import gi
from inkex.gui import asyncme
from inkex.gui.app import GtkApp

from utils.constants import CACHE_DIR, SOURCES, WINDOWS
from utils.import_manager import ImportManager
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW
from utils.stop_watch import StopWatch

from inkex.gui.window import Window
from remote import RemoteSource

from gi.repository import Gtk, Gdk


class ListBoxRowWithData(Gtk.ListBoxRow):
    def __init__(self, icon, name, desc, index, source):
        super().__init__()
        self.index = index
        self.icon = icon
        self.name = name
        self.desc = desc if desc else ""
        self.source = source
        self.set_margin_top(20)
        self.set_size_request(50, 40)
        self.add(Gtk.Label(label=name))


class InkStocksWindow(Window):
    name = "inkstocks_window"
    primary = True

    def __init__(self, gapp: GtkApp):
        super().__init__(gapp)
        css = """
         @import url("theme/instocks.css");
        """
        self.load_css(css)
        self.import_files_btn: Gtk.Button = self.widget('import_files_btn')
        self.import_files_btn.set_sensitive(False)
        self.source_title = self.widget('source_title')
        self.source_desc = self.widget('source_desc')
        self.source_icon = self.widget('source_icon')
        self.progress: Gtk.ProgressBar = self.widget('download_progress')
        self.progress.hide()
        self.no_of_selected = self.widget('no_of_selected')
        self.page_stack: Gtk.Stack = self.widget('page_stack')
        self.import_files_btn.connect('clicked', self.import_files)
        self.sources_lists: Gtk.ListBox = self.widget('sources_lists')

        self.signal_handler = MainHandler(self)
        self.w_tree.connect_signals(self.signal_handler)

        RemoteSource.load(SOURCES)

        self.sources_pixmanager = PixmapManager(CACHE_DIR, scale=3, pref_width=150,
                                                pref_height=150, padding=40, aspect_ratio=SIZE_ASPECT_GROW, )
        self.import_manager = ImportManager(self)
        self.sources = [source(CACHE_DIR, self.import_manager) for source in RemoteSource.sources.values()]
        self.sources_lists.show_all()
        self.sources_results = []
        self.sources_windows = []

        default_source_index = 0
        # create a listboxrow wih data and add to list box
        for index, source in enumerate(self.sources):
            if not source.is_enabled:
                continue
            icon = self.sources_pixmanager.get_pixbuf_for_type(source.icon, "icon", None)
            list_box = ListBoxRowWithData(
                icon, source.name, source.desc, index, source)
            list_box.show_all()
            self.sources_lists.add(list_box)

            if source.is_default:
                default_source_index = index

        # select the source
        self.sources_lists.select_row(
            self.sources_lists.get_row_at_index(default_source_index))

    @staticmethod
    def load_css(data: str):
        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(data.encode('utf8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def import_files(self, *args):
        self.add_and_show_import_window()

    def add_window(self, window_cls, source):
        """if window has not been attached to source, load window"""
        if not source.window and window_cls not in self.sources_windows:
            w = self.gapp.load_window(window_cls.name, source=source, main_window=self)
            self.sources_windows.append(window_cls)

    def show_window(self, window, source):
        """Adds window to the page stack"""

        if not self.page_stack.get_child_by_name(source.name):
            self.page_stack.add_named(window.window, source.name)
        child = self.page_stack.get_child_by_name(source.name)
        self.page_stack.set_visible_child(child)

    def add_and_show_import_window(self):
        self.source_title.set_text("InkStock")
        self.source_desc.set_markup("Save files as zip or import into Inkscape")
        self.sources_lists.set_sensitive(False)
        self.import_files_btn.set_sensitive(False)
        if not self.import_manager.window:
            self.gapp.load_window(self.import_manager.window_cls.name, manager=self.import_manager)
        self.show_window(self.import_manager.window, self.import_manager)
        self.import_manager.show_window()

    def show_sources_window(self):
        self.sources_lists.set_sensitive(True)
        self.import_files_btn.set_sensitive(True)
        row: ListBoxRowWithData = self.sources_lists.get_selected_row()
        self.signal_handler.source_selected(self.sources_lists, row)


class MainHandler:

    def __init__(self, window):
        self.window = window

    def get_selected_source(self) -> RemoteSource:
        return self.window.sources_lists.get_selected_row().source

    def source_selected(self, listbox, row):
        self.window.source_title.set_text(row.name)
        self.window.source_desc.set_markup(row.desc)
        source = self.get_selected_source()

        self.window.source_icon.clear()
        self.window.source_icon.set_from_pixbuf(row.icon)

        self.window.add_window(source.window_cls, source)
        self.window.show_window(source.window, source)
