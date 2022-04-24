from cgitb import handler
from collections import defaultdict
from locale import currency
from mimetypes import init
import os
import gi
from appdirs import user_cache_dir

import inkex
from inkex.gui import asyncme
from inkex.gui.app import GtkApp
from inkex.elements import (
    load_svg, Image, Defs, NamedView, Metadata,
    SvgDocumentElement, StyleElement
)
from inkex.gui.listview import GOBJ, IconView
"""TODO: Override pixelmapmanger's load_from_name_method"""
from inkex.gui.pixmap import PadFilter, PixmapManager, SizeFilter
from inkex.gui.window import Window
from inkex.styles import Style
from remote import RemoteSource, RemotePage, RemoteFile
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from inkex import EffectExtension

SOURCES = os.path.join(os.path.dirname(__file__), 'sources')
LICENSES = os.path.join(os.path.dirname(__file__), 'licenses')
CACHE_DIR = user_cache_dir('inkscape-import-web-image', 'Inkscape')

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

class FlowBoxChildWithData(Gtk.FlowBoxChild):
    def __init__(self, icon, title, index):
        super().__init__()
        self.icon = icon
        self.title = title
        self.index = index
        builder = Gtk.Builder()
        builder.add_objects_from_file(
            'ui/inkstocks.ui', ("result_item", ""))
        self.result_item = builder.get_object("result_item")
        builder.get_object("result_image").set_from_file(self.icon)
        builder.get_object("result_text").set_text(self.title)
        self.add(self.result_item)


class FlowBoxView:
    def __init__(self, widget : Gtk.FlowBox , pixmaps : PixmapManager) -> None:
        self.pixmaps = pixmaps
        self.widget = widget
    
    def clear(self):
        pass
        #self.widget.foreach()
        pass 

    def add_item(self, remote_file: RemoteFile):
        image_pixbuff  = self.pixmaps.get(remote_file.thumbnail , item=remote_file)
        builder = Gtk.Builder()
        builder.add_objects_from_file(
            'ui/inkstocks.ui', ("result_item", ""))
        result_item = builder.get_object("result_item")
        image : Gtk.Image = builder.get_object("result_image")
        image.set_from_pixbuf(image_pixbuff)
        text = builder.get_object("result_text")
        text.set_text(remote_file.string)
        self.widget.add(result_item)
    



class ResultsIconView(IconView):
    """The search results shown as icons"""

    def get_markup(self, item):
        return item.string

    def get_icon(self, item):
        return item.thumbnail

    def setup(self):
        # self._list.set_markup_column(1)
        # self._list.set_pixbuf_column(2)
        # crt, crp = self._list.get_cells()
        # self.crt_notify = crt.connect('notify', self.keep_size)
        super().setup()

    def keep_size(self, crt, *args):
        """Hack Gtk to keep cells smaller"""
        crt.handler_block(self.crt_notify)
        #crt.set_property('width', 150)
        crt.handler_unblock(self.crt_notify)

class Handler:
    pages : dict[str, list[RemotePage]] = {}
    page_items : dict[str, list[RemoteFile]] = {}
    selected_resources = []
    current_page = None

    def __init__(self, window):
        self.window : InkStockWindow = window
   
    def get_selected_source(self) -> RemoteSource:
        return self.window.sources_lists.get_selected_row().source

    def add_page(self, source_name, page):
        self.pages.setdefault(source_name, [])
        self.pages[source_name].append(page)

    def load_more_btn_clicked(self, widget):
        source_name = self.get_selected_source().name
        last_index = len(self.pages[source_name]) - 1
        current_index = self.get_current_page_index()
        if current_index < last_index:
            next_page = self.pages[source_name][current_index+1]
            self.add_search_result(next_page)
            self.current_page = next_page
            self.try_next_page(self.get_selected_source(), current_index + 1)
        elif current_index == last_index:
            self.try_next_page(self.get_selected_source(), current_index + 1)

    def scroll_edge_reached(self, *args, **kwargs):
        pass

    def get_current_page_index(self):
        current_pages = self.pages[self.get_selected_source().name]
        current_index = 0
        for index, page in enumerate(current_pages):
            if self.current_page == page:
                current_index = index
        return current_index

    @asyncme.run_or_none
    def search_changed(self, search_entry):
        source = self.get_selected_source()
        query = search_entry.get_text()
        if query and (len(query) > 2):
            self.async_search(query, source)
            
    @asyncme.run_or_none
    def async_search(self, query, source: RemoteSource):
        """Asyncronous searching in PyPI"""
        self.reset()
        first_page : RemotePage = source.search(query)
        if first_page:
            self.add_search_result(first_page)
            self.add_page(source.name, first_page)
            self.current_page = first_page
            self.try_next_page(source, page_no = 1)

    def reset(self):
        self.pages.clear()
        self.page_items.clear()
        self.selected_resources.clear()
        self.window.results.clear()
        self.current_page = None

    def try_next_page(self, source : RemoteSource , page_no):
        next_page = source.get_page(page_no)
        if next_page and isinstance(next_page, RemotePage):
            self.add_page(source.name, next_page)
            self.window.load_more_btn.show()
        else:
            #TODO: Check if current page is last before hide
            self.window.load_more_btn.hide()

    @asyncme.mainloop_only
    def add_search_result(self, page : RemotePage):
        #we still need to clear incase this method was called from any method at all
        name = page.remote_source.name
        for file in page.get_page_content():
             self.window.results.add_item(file)
             self.page_items.setdefault(name, [])
             self.page_items[name].append(file)  
        
    def source_selected(self, listbox, row):
        self.window.source_title.set_text(row.name)
        self.window.source_desc.set_markup(row.desc)
        source = self.get_selected_source()
        icon = self.window.sources_pixmanager.get(
            source.icon)
        self.window.source_icon.clear()
        self.window.source_icon.set_from_pixbuf(icon)

        if(self.window.search_box.get_text()):
            self.async_search(self.window.search_box.get_text(), source)

    def results_selection_changed(self, box : Gtk.FlowBox):
        selected_items = box.get_selected_children()
        self.selected_resources.clear()
        name = self.get_selected_source().name

        for item in selected_items:
            index = item.get_index()
            resource = self.page_items[name][index]
            self.selected_resources.append(resource)
        enabled = bool(self.selected_resources)
        self.window.widget('import_files_btn').set_sensitive(enabled)
        self.window.widget('no_of_selected').set_text(f"{len(self.selected_resources)} items selected")

    

class InkStockWindow(Window):
    name = "inkstocks_window"

    def __init__(self, gapp : GtkApp):
        super().__init__(gapp)
        css = """
        .results {
            background: white;
        }
        """
        self.load_css(css)
        self.search_spinner = self.widget('search_spinner')
        self.search_spinner.hide()
        self.load_more_btn: Gtk.Button = self.widget('load_more_btn')
        self.load_more_btn.hide()
        self.import_files_btn: Gtk.Button = self.widget('import_files_btn')
        self.import_files_btn.set_sensitive(False)
        self.source_title = self.widget('source_title')
        self.source_desc = self.widget('source_desc')
        self.source_icon = self.widget('source_icon')
        self.search_box = self.widget('search_box')
        self.page_stack : Gtk.Stack = self.widget('page_stack')
        
        
        self.sources_lists : Gtk.ListBox = self.widget('sources_lists')

        self.signal_handler = Handler(self)
        self.w_tree.connect_signals(self.signal_handler)

        RemoteSource.load(SOURCES)
        self.sources_pixmanager = PixmapManager(SOURCES, filters=[
            SizeFilter(size=48),
            PadFilter(size=(0, 60))
        ])
        self.sources_lists.show_all()
        default_index = 0

        
        for index, (key, source) in enumerate(RemoteSource.sources.items()):
            if not source.is_enabled:
                continue
            list_box = ListBoxRowWithData(
                self.sources_pixmanager.get(source.icon), source.name, source.desc, index, source(CACHE_DIR))
            list_box.show_all()
            self.sources_lists.add(list_box)
            if source.is_default:
                default_index = index
        self.sources_lists.select_row(
            self.sources_lists.get_row_at_y(default_index))

        results_pixmanager = PixmapManager(CACHE_DIR, load_size=(400, 400), filters=[
            SizeFilter(size=70, resize_mode=1),
            PadFilter(size=(0, 150))
        ])
         
        resultBuilder = Gtk.Builder()
        resultBuilder.add_objects_from_file(
           "ui/inkstocks.ui", ("flow_scroll_window_copy", ""))
        self.results_widget = resultBuilder.get_object("results_flow")
        #self.results = ResultsIconView(self.results_widget, results_pixmanager, liststore = RemoteFile)
        self.results = FlowBoxView(self.results_widget, results_pixmanager)
        
        resultBuilder.connect_signals(self.signal_handler)
        self.page_stack.add_named(
            resultBuilder.get_object("flow_scroll_window_copy"), 'results_window')
        
    def load_css(self, data : str):
        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(data.encode('utf8'))
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_prov,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


class InkStockApp(GtkApp):
    app_name = "InkStock"
    ui_dir = "ui"
    ui_file = "inkstocks"
    glade_dir = os.path.join(os.path.dirname(__file__))
    windows = [InkStockWindow]

class InkstockExtension(EffectExtension):

    def merge_defs(self, defs):
        """Add all the items in defs to the self.svg.defs"""
        target = self.svg.defs
        for child in defs:
            if isinstance(child, StyleElement):
                continue  # Already appled in merge_stylesheets()
            target.append(child)

    def merge_stylesheets(self, svg):
        """Because we don't want conflicting style-sheets (classes, ids, etc) we scrub them"""
        elems = defaultdict(list)
        # 1. Find all styles, and all elements that apply to them
        for sheet in svg.getroot().stylesheets:
            for style in sheet:
                xpath = style.to_xpath()
                for elem in svg.xpath(xpath):
                    elems[elem].append(style)
                    # 1b. Clear possibly conflicting attributes
                    if '@id' in xpath:
                        elem.set_random_id()
                    if '@class' in xpath:
                        elem.set('class', None)
        # 2. Apply each style cascade sequentially
        for elem, styles in elems.items():
            output = Style()
            for style in styles:
                output += style
            elem.style = output + elem.style

    def import_svg(self, new_svg):
        """Import an svg file into the current document"""
        self.merge_stylesheets(new_svg)
        for child in new_svg.getroot():
            if isinstance(child, SvgDocumentElement):
                yield from self.import_svg(child)
            elif isinstance(child, StyleElement):
                continue  # Already applied in merge_stylesheets()
            elif isinstance(child, Defs):
                self.merge_defs(child)
            elif isinstance(child, (NamedView, Metadata)):
                pass
            else:
                yield child

    def import_from_file(self, filename):
        if not filename or not os.path.isfile(filename):
            return
        with open(filename, 'rb') as fhl:
            head = fhl.read(100)
            if b'<?xml' in head or b'<svg' in head:
                new_svg = load_svg(head + fhl.read())
                # Add each object to the container
                objs = list(self.import_svg(new_svg))

                if len(objs) == 1 and isinstance(objs[0], inkex.Group):
                    # Prevent too many groups, if item aready has one.
                    container = objs[0]
                else:
                    # Make a new group to contain everything
                    container = inkex.Group()
                    for child in objs:
                        container.append(child)

                # Retain the original filename as a group label
                container.label = os.path.basename(filename)
                # Apply unit transformation to keep things the same sizes.
                container.transform.add_scale(self.svg.unittouu(1.0)
                                              / new_svg.getroot().unittouu(1.0))

            else:
                container = self.import_raster(filename, fhl)

            self.svg.get_current_layer().append(container)

            # Make sure that none of the new content is a layer.
            for child in container.descendants():
                if isinstance(child, inkex.Group):
                    child.set("inkscape:groupmode", None)

    def effect(self) :
        InkStockApp(start_loop=True,)
        

    @staticmethod
    def get_type(path, header):
        """Basic magic header checker, returns mime type"""
        # Taken from embedimage.py
        for head, mime in (
            (b'\x89PNG', 'image/png'),
            (b'\xff\xd8', 'image/jpeg'),
            (b'BM', 'image/bmp'),
            (b'GIF87a', 'image/gif'),
            (b'GIF89a', 'image/gif'),
            (b'MM\x00\x2a', 'image/tiff'),
            (b'II\x2a\x00', 'image/tiff'),
        ):
            if header.startswith(head):
                return mime
        return None

if __name__ == '__main__':
    InkStockApp(start_loop=True)
    #InkstockExtension().run()
