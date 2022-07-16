import asyncio
import os
import shutil
from pathlib import Path

import requests

from core.utils import asyncme
from sources.remote import RemoteSource, RemoteFile, SourceType
from gi.repository import Gtk

from core.network.adapter import FileAdapter
from core.constants import CACHE_DIR
from tasks.task import add_task_to_queue, task_loop
from windows.import_window import ImportWindow, ImportItem
from windows.options_window import OptionsWindow, OptionType, OptionsChangeListener


async def apply_tasks_to_file(file: RemoteFile, file_path: str):
    for task in file.tasks:
        await task.do_task(file_path)


class ImportManager(OptionsChangeListener):
    name = "import_manager"
    window_cls = ImportWindow
    window: ImportWindow = None

    def __init__(self, ink_window):
        # contains final list of sources and files that would be imported
        self.sources: dict[RemoteSource, set[RemoteFile]] = {}

        self.ink_window = ink_window
        self.ink_ext = self.ink_window.gapp.ext
        self.files_saved: dict[RemoteSource, set] = {}
        self.files: dict[RemoteSource, set] = {}
        self.session = requests.session()
        self.session.mount('file://', FileAdapter())

        headers = {
            "user-agent": "InkStock"
        }
        self.session.headers.update(headers)

        # ====== Options Window ========= #
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("sources", "Sources to import from", OptionType.TEXTVIEW)

    def show_window(self):
        # Merge saved files and temporarily selected files together
        sources: dict[RemoteSource, set] = {}
        for source, files in self.files_saved.items():
            sources.setdefault(source, set())
            for file in files:
                sources[source].add(file)
        for source, files in self.files.items():
            sources.setdefault(source, set())
            for file in files:
                sources[source].add(file)

        self.sources.clear()
        self.sources = sources

        # ========== Prepare Options Window ========== #
        # remove any previously added options if present
        self.options_window.remove_option("sources_select")
        self.options_window.remove_option("import_all")
        self.options_window.remove_option("import_zip")
        self.options_window.remove_option("back_to_sources")

        # create new
        select_option = self.options_window.set_option("sources_select",
                                                       list(map(lambda x: x.name + f" ({len(self.sources[x])})",
                                                                self.sources.keys())), OptionType.SELECT,
                                                       show_separator=False)
        if self.ink_ext:
            self.options_window.set_option("import_all", self.import_all, OptionType.BUTTON,
                                           "Import into Inkscape", show_separator=False)
        self.options_window.set_option("import_zip", self.show_zip_dialog, OptionType.BUTTON,
                                       "Save as zip", show_separator=False)
        self.options_window.set_option("back_to_sources", self.back_to_sources, OptionType.BUTTON,
                                       "Back to sources", show_separator=False)

        # select first item from sources to import
        select_option.view.select_row(
            select_option.view.get_row_at_index(0))

    def back_to_sources(self, name):
        self.ink_window.show_sources_window()

    def remove_source(self, button, item: ImportItem):
        for source, items in self.files_saved.items():
            if item.data in items:
                self.files_saved[source].remove(item.data)
                if len(self.files_saved[source]) == 0:
                    self.files_saved.pop(source)
                break

        for source, items in self.sources.items():
            if item.data in items:
                self.sources[source].remove(item.data)
        self.window.results.remove_item(item)

    def on_change(self, options):
        if "sources_select" in options:
            selected_source = options["sources_select"]
            for source, files in self.sources.items():
                if selected_source.startswith(source.name):
                    self.refresh(files, source)
                    break

    def refresh(self, files, source):
        pix_manager = source.pix_manager
        self.window.results.clear()
        self.window.results.add_items(files, pix_manager)

    def save_file(self, source, file):
        self.files_saved.setdefault(source, set())
        if file:
            self.files_saved[source].add(file)
        self.update_import_btn_status()

    def add_files(self, source, files):
        self.files.setdefault(source, set())
        if len(files) > 0:
            self.files[source].clear()
            for file in files:
                self.files[source].add(file)
        else:
            self.files.pop(source)

        self.update_import_btn_status()

    def update_import_btn_status(self):
        sel_plus_saved = set()

        for item in self.files.values():
            sel_plus_saved.update(item)
            # no_of_items += len(item)
        for item in self.files_saved.values():
            sel_plus_saved.update(item)
            # no_of_items += len(item)
        no_of_items = len(sel_plus_saved)
        self.ink_window.no_of_selected.set_text(f"{no_of_items} items selected")
        if no_of_items > 0:
            self.ink_window.import_files_btn.set_sensitive(True)
        else:
            self.ink_window.import_files_btn.set_sensitive(False)

    def show_zip_dialog(self, name):
        dialog = Gtk.FileChooserDialog(
            title="Save zip as", transient_for=self.ink_window.window,
            action=Gtk.FileChooserAction.SAVE
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        home_dir = os.path.expanduser('~')
        dialog.set_current_folder(home_dir)
        dialog.set_current_name("untitled.zip")
        dialog.set_default_size(800, 400)

        f = Gtk.FileFilter()
        f.set_name("Zip files")
        f.add_mime_type("application/zip")
        dialog.add_filter(f)

        response = dialog.run()
        filename = None
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        dialog.destroy()
        self.set_window_sensitive(False)

        # self.import_zip(filename)

        def cb(result, error):
            if error:
                print(f"Error occurred during download: {error}")

            self.set_window_sensitive(True)
            asyncme.mainloop_only(self.ink_window.progress.hide)()

        asyncio.run_coroutine_threadsafe(add_task_to_queue(self.import_zip, cb, filename), loop=task_loop)

    async def import_zip(self, save_filename):
        basename = Path(save_filename).stem
        temp_dir = os.path.join(CACHE_DIR, basename)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        for source, files in self.sources.items():
            path = os.path.join(temp_dir, source.source_type.value)
            if not os.path.exists(path):
                os.makedirs(path)
            for file in files:
                await self.download(file, os.path.join(path, file.file_name))
        save_dir = os.path.dirname(save_filename)
        shutil.make_archive(os.path.join(save_dir, basename), "zip", root_dir=temp_dir)
        shutil.rmtree(temp_dir, ignore_errors=True)

    @asyncme.mainloop_only
    def set_window_sensitive(self, sensitive: bool):
        if sensitive:
            self.window.window.set_sensitive(True)
            self.window.window.set_opacity(1)
        else:
            self.window.window.set_sensitive(False)
            self.window.window.set_opacity(0.5)

    async def download(self, file, file_path):
        url = file.get_file()
        name = os.path.basename(file_path)
        bytes_downloaded = 0
        with open(file_path, mode="wb") as out:
            with self.session.get(url, stream=True) as r:
                total = r.headers["content-length"]
                total = int(total)
                for data in r.iter_content(chunk_size=5000):
                    bytes_downloaded += len(data)
                    out.write(data)
                    self.show_progress(bytes_downloaded, total, name)

        await apply_tasks_to_file(file, file_path)

    @asyncme.mainloop_only
    def show_progress(self, bytes_downloaded, total, name):
        self.ink_window.progress.show()
        if total:
            percent = bytes_downloaded / total
            self.ink_window.progress.set_show_text(True)
            self.ink_window.progress.set_text(f"Fetching {name}...")
            self.ink_window.progress.set_fraction(percent)
        else:
            self.ink_window.progress.set_show_text(True)
            self.ink_window.progress.set_text(f"Fetching {name}...")
            self.ink_window.progress.pulse()

    def import_all(self, name):
        self.set_window_sensitive(False)

        def cb(result, error):
            if error:
                print(f"Error occurred during import: {error}")
            self.set_window_sensitive(True)
            asyncme.mainloop_only(self.ink_window.progress.hide)()

        asyncio.run_coroutine_threadsafe(add_task_to_queue(self.import_into_inkscape, cb), loop=task_loop)

    async def import_into_inkscape(self):
        import_temp_dir = os.path.join(CACHE_DIR, "import_tmp")
        if os.path.exists(import_temp_dir):
            shutil.rmtree(import_temp_dir)
        for source, files in self.sources.items():
            # importing font into Inkscape not supported yet
            if source.source_type == SourceType.FONT:
                continue
            path = os.path.join(import_temp_dir, source.source_type.value)
            if not os.path.exists(path):
                os.makedirs(path)
            for file in files:
                file_to_import = os.path.join(path, file.file_name)
                await self.download(file, file_to_import)
                self.show_progress(None, None, f" Importing {file.file_name}...")
                self.ink_ext.import_from_file(file_to_import)
            shutil.rmtree(import_temp_dir, ignore_errors=True)
