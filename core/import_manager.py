import asyncio
import inspect
import os
import shutil
from asyncio import Queue
from pathlib import Path
from threading import Thread

import requests
from gi.repository import Gtk

from core.constants import CACHE_DIR
from core.network.adapter import FileAdapter
from core.utils import asyncme
from sources.source import RemoteSource, SourceType
from sources.source_file import RemoteFile
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

        # start async tasks queue in background thread
        self.download_task_queue: Queue = None
        self.download_task_loop = asyncio.new_event_loop()
        task_thread = Thread(target=self.start_background_loop, daemon=True)
        task_thread.start()
        while not self.download_task_loop.is_running():
            pass  # simply waiting loop to start

    def start_background_loop(self) -> None:
        asyncio.set_event_loop(self.download_task_loop)
        self.download_task_queue = Queue()
        self.download_task_loop.run_until_complete(self.consume_task())

    def add_task_to_queue(self, fn, callback, *args, **kwargs):
        asyncio.run_coroutine_threadsafe(self.download_task_queue.put((fn, callback, args, kwargs)),
                                         loop=self.download_task_loop)

    async def consume_task(self):
        while True:
            fn, callback, args, kwargs = await self.download_task_queue.get()
            try:
                if inspect.iscoroutinefunction(fn):
                    result = await fn(*args, **kwargs)
                else:
                    result = fn(*args, **kwargs)
                callback(result=result, error=None)
            except Exception as err:
                callback(result=None, error=err)
            self.download_task_queue.task_done()

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

        # create new
        select_option = self.options_window.set_option("sources_select",
                                                       list(map(lambda x: x.name + f" ({len(self.sources[x])})",
                                                                self.sources.keys())), OptionType.SELECT,
                                                       show_separator=False)
        if self.ink_ext:
            self.options_window.set_option("import_all", self.import_all, OptionType.BUTTON,
                                           "Import into Inkscape", show_separator=False, allow_multiple=False)
        self.options_window.set_option("import_zip", self.show_zip_dialog, OptionType.BUTTON,
                                       "Save as zip", show_separator=False, allow_multiple=False)
        self.options_window.set_option("import_folder", self.show_folder_dialog, OptionType.BUTTON,
                                       "Save to Folder", show_separator=False, allow_multiple=False)
        self.options_window.set_option("back_to_sources", self.back_to_sources, OptionType.BUTTON,
                                       "Back to sources", show_separator=False, allow_multiple=False)

        # select first item from sources to import
        select_option.list.select_row(
            select_option.list.get_row_at_index(0))

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

    def show_folder_dialog(self, name):
        dialog = Gtk.FileChooserDialog(
            title="Save in folder", transient_for=self.ink_window.window,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK
        )
        home_dir = os.path.expanduser('~')
        dialog.set_current_folder(home_dir)
        dialog.set_default_size(800, 400)
        response = dialog.run()
        filename = None
        if response == Gtk.ResponseType.OK:
            filename = dialog.get_filename()
        dialog.destroy()
        if not filename:
            return
        self.set_window_sensitive(False)

        def cb(result, error):
            if error:
                print(f"Error occurred during download: {error}")

            self.set_window_sensitive(True)
            asyncme.mainloop_only(self.ink_window.progress.hide)()

        self.add_task_to_queue(self.save_to_folder, cb, filename)

    async def save_to_folder(self, folder_path):
        for source, files in self.sources.items():
            path = os.path.join(folder_path, source.source_type.value)
            if not os.path.exists(path):
                os.makedirs(path)
            for file in files:
                await self.download(file, os.path.join(path, file.file_name))

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
        if not filename:
            return
        self.set_window_sensitive(False)

        def cb(result, error):
            if error:
                print(f"Error occurred during download: {error}")

            self.set_window_sensitive(True)
            asyncme.mainloop_only(self.ink_window.progress.hide)()

        self.add_task_to_queue(self.import_zip, cb, filename)

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
                total = r.headers.get("content-length")
                total = int(total) if total else None
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

        self.add_task_to_queue(self.import_into_inkscape, cb)

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
