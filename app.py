from typing import List
from unittest import result
from inkex.gui.listview import IconView
from inkex.gui.pixmap import PadFilter, PixmapFilter, PixmapManager, SizeFilter
from inkex.gui import asyncme
from import_sources import RemotePage, RemoteSource
from gi.repository import Gtk
import os

import gi
from appdirs import user_cache_dir
gi.require_version("Gtk", "3.0")

settings = Gtk.Settings.get_default()
# if you want use dark theme, set second arg to True
settings.set_property("gtk-application-prefer-dark-theme", False)


SOURCES = os.path.join(os.path.dirname(__file__), 'sources')
LICENSES = os.path.join(os.path.dirname(__file__), 'licenses')
CACHE_DIR = user_cache_dir('inkscape-import-web-image', 'Inkscape')


class FlowBoxChildWithData(Gtk.FlowBoxChild):
    def __init__(self, icon, title, index):
        super().__init__()
        self.icon = icon
        self.title = title
        self.index = index
        builder = Gtk.Builder()
        builder.add_objects_from_file(
            'icons/external_resources.glade', ("result_item", ""))
        self.result_item = builder.get_object("result_item")
        builder.get_object("result_image").set_from_file(self.icon)
        builder.get_object("result_text").set_text(self.title)
        self.add(self.result_item)


class ListBoxRowWithData(Gtk.ListBoxRow):
    def __init__(self, icon, name, desc, index):
        super().__init__()
        self.index = index
        self.icon = icon
        self.name = name
        self.desc = desc if desc else ""
        self.set_margin_top(20)
        self.set_size_request(50, 40)
        self.add(Gtk.Label(label=name))


class ResultsIconView(IconView):
    """The search results shown as icons"""

    def get_markup(self, item):
        return item.string

    def get_icon(self, item):
        return item.icon

    def setup(self):
        self._list.set_markup_column(1)
        self._list.set_pixbuf_column(2)
        crt, crp = self._list.get_cells()
        self.crt_notify = crt.connect('notify', self.keep_size)
        super().setup()

    def keep_size(self, crt, *args):
        """Hack Gtk to keep cells smaller"""
        crt.handler_block(self.crt_notify)
        crt.set_property('width', 150)
        crt.handler_unblock(self.crt_notify)


class TestWindow:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        builder = Gtk.Builder()

        builder.add_from_file("icons/external_resources.glade")
        self.window = builder.get_object("window")
        builder.connect_signals(self)
        self.window.connect('destroy', Gtk.main_quit)
        self.widget = builder.get_object
        self.search_spinner = self.widget('search_spinner')
        self.search_spinner.hide()
        self.source_items = []
        self.previous_page_btn: Gtk.Button = self.widget('previous_page_btn')
        self.previous_page_btn.hide()
        self.next_page_btn: Gtk.Button = self.widget('next_page_btn')
        self.next_page_btn.hide()
        self.import_files_btn: Gtk.Button = self.widget('import_files_btn')
        self.import_files_btn.set_sensitive(False)
        self.source_title = self.widget('source_title')
        self.source_desc = self.widget('source_desc')
        self.source_icon = self.widget('source_icon')
        self.search_box = self.widget('search_box')
        self.page_stack = self.widget('page_stack')

        self.sources_lists = self.widget('sources_lists')
        self.resources = []
        self.selected_resources = []
        self.page_handler = PageHandler(self)

        RemoteSource.load(SOURCES)
        self.pix = PixmapManager(SOURCES, filters=[
            SizeFilter(size=48),
            PadFilter(size=(0, 60))
        ])
        self.sources_lists.show_all()
        default_index = 0

        for x, (key, source) in enumerate(RemoteSource.sources.items()):
            if not source.is_enabled:
                continue
            # We add them in GdkPixbuf, string, string format (see glade file)
            self.source_items.append(
                [self.pix.get(source.icon), source.name, key])
            list_box = ListBoxRowWithData(
                self.pix.get(source.icon), source.name, source.desc, x)
            list_box.show_all()
            self.sources_lists.add(list_box)
            self.page_handler.init_page_store(source)
            if source.is_default:
                default_index = x

        self.sources_lists.select_row(
            self.sources_lists.get_row_at_y(default_index))

        pixmaps = PixmapManager(CACHE_DIR, load_size=(400, 400), filters=[
            SizeFilter(size=70, resize_mode=1),
            PadFilter(size=(0, 150))
        ])
         
        
        resultBuilder = Gtk.Builder()
        resultBuilder.add_objects_from_file(
            "icons/external_resources.glade", ("flow_scroll_window", ""))
        self.results_widget = resultBuilder.get_object("results")
        self.results = ResultsIconView(self.results_widget, pixmaps)
        resultBuilder.connect_signals(self)
        self.page_stack.add_named(
            resultBuilder.get_object("flow_scroll_window"), 'page1')

    def source_selected(self, listbox, row):
        self.source_title.set_text(row.name)
        self.source_desc.set_markup(row.desc)
        source = list(RemoteSource.sources.values())[row.index]
        icon = self.pix.get(
            source.icon)
        self.source_icon.clear()
        self.source_icon.set_from_pixbuf(icon)
        self.page_handler.on_source_changed(source)

        if(self.search_box.get_text()):
            self.async_search(self.search_box.get_text())
    
    
    def get_selected_source(self) -> RemoteSource:
        index = self.sources_lists.get_selected_row().index
        return list(RemoteSource.sources.values())[index](CACHE_DIR)

    @asyncme.run_or_none
    def search_changed(self, search_entry):
        query = search_entry.get_text()
        if len(query) > 2:
            from threading import Timer
            Timer(2, self.async_search, [query]).start()

    @asyncme.run_or_none
    def async_search(self, query):
        """Asyncronous searching in PyPI"""
        self.results.clear()
        self.resources.clear()
        self.page_handler.clear_pages()
        self.page_handler.update_buttons()
        self.search_started()
        for resource in self.get_selected_source().file_search(query):
            self.add_search_result(resource)
        self.search_finished()

    @asyncme.mainloop_only
    def add_search_result(self, resource):
        """Adding things to Gtk must be done in mainloop"""
        if isinstance(resource, RemotePage):
            
            return self.set_next_page(resource)
        self.resources.append(resource)
        self.results.add_item(resource)


    def results_selection_changed(self, items: IconView):
        selected_items = items.get_selected_items()
        self.selected_resources.clear()
        for item in selected_items:
            index = item.get_indices()[0]
            self.selected_resources.append(self.resources[index])
        enabled = bool(self.selected_resources)
        self.widget('import_files_btn').set_sensitive(enabled)

    def search_started(self):
        self.search_spinner.start()
        self.search_spinner.show()

    @asyncme.mainloop_only
    def search_finished(self):
        """After everything, finish the search"""
        self.search_spinner.hide()
        self.search_spinner.stop()
    
    @asyncme.run_or_none
    def set_next_page(self, item):
        self.page_handler.add_page(item, self.get_selected_source())

    def show_page(self, item):
        if item:
            self.results.clear()
            self.resources.clear()
            self.search_started()
            self.async_show_page(item)

    @asyncme.run_or_none
    def async_show_page(self, item):
        for resource in item.get_page_content():
            self.add_search_result(resource)
        self.search_finished()

    def img_import(self, widget=None):
        """Apply the selected image and quit"""
        to_exit = True
        for resource in self.selected_resources:
            self.select_func(resource.get_file())
            # XXX This pagination control is not good. Replace it with normal controls.
            # elif isinstance(item, RemotePage):
        if to_exit:
            self.exit()


class PageHandler:
    current_page_index: dict[str, int] = {}
    page_store: dict[str, list] = {}

    def __init__(self, app: TestWindow):
        self.app = app
        self.app.next_page_btn.connect('clicked', self.next_page_clicked)
        self.app.previous_page_btn.connect(
            'clicked', self.previous_page_clicked)

    def has_next(self):
        current_source_name = self.app.get_selected_source().name
        pages: list = self.page_store[current_source_name]
        index = self.current_page_index[current_source_name]
        return len(pages) - 1 >= index

    def has_previous(self):
        current_source_name = self.app.get_selected_source().name
        index = self.current_page_index[current_source_name]
        return index  > 0

    def next_page_clicked(self, widget):
        """Displays next page stored in a 0 - based list of pages"""
        current_source_name = self.app.get_selected_source().name
        pages: list = self.page_store[current_source_name]
        self.app.show_page(pages[self.current_page_index[current_source_name]])
        self.current_page_index[current_source_name] += 1
        self.update_buttons()

    def previous_page_clicked(self, widget):
        current_source_name = self.app.get_selected_source().name
        pages: list = self.page_store[current_source_name]
        self.current_page_index[current_source_name] -= 1
        pages.pop()
        self.app.show_page(pages[self.current_page_index[current_source_name] - 1])
        self.update_buttons()
        

    def update_buttons(self):
        if self.has_previous():
            self.app.previous_page_btn.show()
        else:
            self.app.previous_page_btn.hide()
        if self.has_next():
            self.app.next_page_btn.show()
        else:
            self.app.next_page_btn.hide()

    def init_page_store(self, source):
        self.page_store[source.name] = []
        self.current_page_index[source.name] = 0

    def add_page(self, page: RemotePage, source: RemoteSource):
        page_list: list = self.page_store[source.name]
        page_list.append(page)
        self.update_buttons()
        
    def on_source_changed(self, source: RemoteSource):
        pages: list = self.page_store[source.name]
        index = self.current_page_index[source.name]
        if pages:
            page = pages[index]
            self.app.show_page(page)
            self.app.next_page_btn.set_sensitive(self.has_next())
            self.app.previous_page_btn.set_sensitive(self.has_previous())

    def clear_pages(self):
        for (_, pages) in self.page_store.items():
            pages.clear()
        for page in self.current_page_index.keys():
            self.current_page_index[page] = 0

TestWindow().window.show()
Gtk.main()
