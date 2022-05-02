import gi
from inkex.gui import asyncme
from inkex.gui.window import ChildWindow
from utils.constants import CACHE_DIR
from remote import RemoteFile, RemotePage, RemoteSource
from utils.pixelmap import PixmapManager, load_css

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk


class ResultsWindow(ChildWindow):
    name = "results_window"

    def __init__(self, gapp):
        super().__init__(gapp)
        self.handler = None
        self.results = None
        self.flowbox = self.widget("results_flow")
        self.load_more_btn = self.widget("load_more_btn")

    def init(self, parent=None, **kwargs):
        self.handler = ResultsHandler(self, kwargs["source"])
        self.w_tree.connect_signals(self.handler)
        super().init(parent, **kwargs)

    def load_widgets(self, *args, **kwargs):
        pixmaps = kwargs.get("pixmaps", None)
        if not pixmaps:
            pixmaps = PixmapManager(CACHE_DIR)
        self.results = FlowBoxView(self.flowbox, pixmaps)
        # self.load_more_btn.connect("clicked", self.handler.load_more_btn_clicked)


class ResultsHandler:

    def __init__(self, window, source):
        self.source: RemoteSource = source
        self.window = window
        self.pages: list[RemotePage] = []
        self.page_items: list[RemoteFile] = []
        self.selected_resources = []
        self.current_page = None

    def get_current_page_index(self):
        current_index = 0
        for index, page in enumerate(self.pages):
            if self.current_page == page:
                current_index = index
        return current_index

    def results_selection_changed(self, box: Gtk.FlowBox):
        selected_items = box.get_selected_children()
        self.selected_resources.clear()

        for item in selected_items:
            self.selected_resources.append(item.data)

    def add_page(self, page):
        self.pages.append(page)
        first_page = len(self.pages) == 1
        if first_page:
            for file in page.get_page_content():
                self.add_page_item(file)
            self.current_page = page
            self.try_next_page(self.source, page_no=1)

    def clear(self):
        if self.page_items:
            self.window.results.clear()
        self.pages.clear()
        self.page_items.clear()
        self.current_page = None
        self.selected_resources.clear()

    def add_page_item(self, file: RemoteFile):
        self.window.results.add_item(file)
        self.page_items.append(file)

    def load_more_btn_clicked(self, widget):
        last_index = len(self.pages) - 1
        current_index = self.get_current_page_index()
        if current_index < last_index:
            next_page = self.pages[current_index + 1]
            for file in next_page.get_page_content():
                self.add_page_item(file)
            self.current_page = next_page
            self.try_next_page(self.source, current_index + 1)
        elif current_index == last_index:
            self.try_next_page(self.source, current_index + 1)

    def scroll_edge_reached(self, *args, **kwargs):
        pass

    def try_next_page(self, source: RemoteSource, page_no):
        no_of_pages = len(self.pages)
        source.get_page(page_no)
        if len(self.pages) > no_of_pages:
            self.window.load_more_btn.show()
        else:
            self.window.load_more_btn.hide()


class FlowBoxChildWithData(Gtk.FlowBoxChild):
    def __init__(self, data):
        super().__init__()
        self.data = data
        # self.add(widget)
        self.show_all()


class FlowBoxView:
    def __init__(self, widget: Gtk.FlowBox, pixmaps) -> None:
        self.builder = Gtk.Builder()
        self.pixmaps = pixmaps
        self.widget = widget

    @asyncme.mainloop_only
    def clear(self):
        def remove(child: Gtk.Widget):
            child.destroy()

        self.widget.foreach(remove)

    @asyncme.mainloop_only
    def add_item(self, remote_file: RemoteFile):
        self.pixmaps.get_pixbuf_from_file(remote_file, self.callback)

    @asyncme.mainloop_only
    def callback(self, pix_path, remote_file):
        item_id = "id" + str(remote_file.id)
        css = "#" + item_id + '''{
            background-size: cover;
            background-origin: content-box;
            background: url("''' + pix_path + '''") no-repeat;
        }
    '''
        load_css(css)
        child = FlowBoxChildWithData(remote_file)
        child.set_size_request(self.pixmaps.grid_item_width, self.pixmaps.grid_item_height)
        child.set_hexpand(False)
        child.set_vexpand(False)
        child.set_name(item_id)
        self.widget.add(child)
        return

        if True:
            self.builder.add_objects_from_file(
                'ui/results_window.ui', ("result_item", ""))
            result_item = self.builder.get_object("result_item")
            result_item.set_hexpand(False)
            image: Gtk.Image = self.builder.get_object("result_image")
            image.set_from_pixbuf(image_pixbuff)
            text = self.builder.get_object("result_text")
            text.set_text(remote_file.string)
            self.widget.add(FlowBoxChildWithData(result_item, remote_file))

        else:
            self.builder.add_objects_from_file(
                'ui/results_window.ui', ("result_image_only", ""))
            result_item = self.builder.get_object("result_image_only")
            result_item.set_from_pixbuf(image_pixbuff)
            flow_box = FlowBoxChildWithData(result_item, remote_file)
            flow_box.set_hexpand(False)
            style = flow_box.get_style_context()
            style.add_class("transparent")
            self.widget.set_homogeneous(False)
            self.widget.add(flow_box)
