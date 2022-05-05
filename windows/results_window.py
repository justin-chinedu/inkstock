from typing import Set

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
        self.handler: ResultsHandler = None

    @asyncme.mainloop_only
    def show_window(self, window, name):
        page_stack: Gtk.Stack = self.window

        if not page_stack.get_child_by_name(name):
            page_stack.add_named(window, name)
        child = page_stack.get_child_by_name(name)
        if page_stack.get_visible_child() != child:
            page_stack.set_visible_child(child)

    def init(self, parent=None, **kwargs):
        self.handler = ResultsHandler(self, kwargs["source"])
        self.w_tree.connect_signals(self.handler)
        super().init(parent, **kwargs)

    def load_widgets(self, *args, **kwargs):
        pixmaps = kwargs.get("pixmaps", None)
        if not pixmaps:
            pixmaps = PixmapManager(CACHE_DIR)
        self.multiview = MultiItemView(self, pixmaps)
        self.singleview = SingleItemView(self, pixmaps)

    # self.load_more_btn.connect("clicked", self.handler.load_more_btn_clicked)


class FlowBoxChildWithData(Gtk.FlowBoxChild):
    def __init__(self, data, show_text=True):
        super().__init__()
        self.data = data
        builder = Gtk.Builder()
        builder.add_objects_from_file(
            'ui/results_window.ui', ["view_image_btn", "view_icon", "result_item"])
        self.button: Gtk.Button = builder.get_object("view_image_btn")
        self.label: Gtk.Label = builder.get_object("result_text")
        self.image: Gtk.Overlay = builder.get_object("result_image")
        self.result: Gtk.Overlay = builder.get_object("result_item")
        self.button.hide()
        self.add(self.result)
        self.show()


class SingleItemView:
    def __init__(self, window: ResultsWindow, pixmaps: PixmapManager) -> None:
        self.builder = Gtk.Builder()
        self.pixmaps = pixmaps
        self.window = window
        self.builder.add_objects_from_file(
            'ui/results_window.ui', ["results_single_view"])
        self.single_view = self.builder.get_object("results_single_view")
        self.image: Gtk.Image = self.builder.get_object("results_single_image")
        self.text = self.builder.get_object("results_single_text")
        self.list: Gtk.FlowBox = self.builder.get_object("results_single_list")
        self.builder.connect_signals(window.handler)
        self.single_view.show()

    @asyncme.mainloop_only
    def clear(self):
        def remove(child: Gtk.Widget):
            child.destroy()

        self.list.foreach(remove)

    def show_view(self):
        self.window.show_window(self.single_view, "singleview")

    @asyncme.mainloop_only
    def show_previews(self, remote_files, selected_file):
        self.list.set_min_children_per_line(len(remote_files))
        for remote_file in remote_files:
            self.pixmaps.get_pixbuf_from_file_for_previews(remote_file, selected_file, self.callback)

    def show_file(self, file):
        self.pixmaps.get_pixbuf_for_preview(file, self.__set_image)

    @asyncme.mainloop_only
    def __set_image(self, pixbuf):
        self.image.set_from_pixbuf(pixbuf)

    @asyncme.mainloop_only
    def callback(self, pix_path, remote_file, selected_file):
        item_id = "id" + str(remote_file.id)
        css = self.pixmaps.style
        css = css.format(id=item_id, url=pix_path)

        child = FlowBoxChildWithData(remote_file)
        child.set_size_request(self.pixmaps.preview_item_width, self.pixmaps.preview_item_height)
        child.set_hexpand(False)
        child.set_vexpand(False)
        child.get_style_context().add_class(item_id)
        load_css(css)
        self.list.add(child)
        if remote_file.id == selected_file.id:
            self.list.select_child(child)


class MultiItemView:
    def __init__(self, window: ResultsWindow, pixmaps) -> None:
        self.builder = Gtk.Builder()
        self.pixmaps = pixmaps
        self.window = window
        self.builder.add_objects_from_file(
            'ui/results_window.ui', ["results_multi_view"])
        self.multi_view = self.builder.get_object("results_multi_view")
        self.flow_box = self.builder.get_object("results_flow")
        self.load_more_btn = self.builder.get_object("load_more_btn")
        self.builder.connect_signals(window.handler)
        self.multi_view.show()

    @asyncme.mainloop_only
    def clear(self):
        def remove(child: Gtk.Widget):
            child.destroy()

        self.flow_box.foreach(remove)

    def show_view(self):
        self.window.show_window(self.multi_view, "multiview")

    def add_item(self, remote_file: RemoteFile):
        self.pixmaps.get_pixbuf_from_file(remote_file, self.callback)

    @asyncme.mainloop_only
    def callback(self, pix_path, remote_file):
        item_id = "id" + str(remote_file.id)
        css = self.pixmaps.style
        css = css.format(id=item_id, url=pix_path)

        child = FlowBoxChildWithData(remote_file)
        child.result.set_size_request(self.pixmaps.grid_item_width, self.pixmaps.grid_item_height)
        child.result.set_hexpand(False)
        child.result.set_vexpand(False)
        child.result.get_style_context().add_class(item_id)
        child.label.set_text(remote_file.string)
        # child.set_name(item_id)
        child.button.connect("clicked", self.window.handler.view_image, child)
        child.button.hide()
        load_css(css)
        self.flow_box.add(child)

        # if True:
        #     self.builder.add_objects_from_file(
        #         'ui/results_window.ui', ("result_item", ""))
        #     result_item = self.builder.get_object("result_item")
        #     result_item.set_hexpand(False)
        #     image: Gtk.Image = self.builder.get_object("result_image")
        #     image.set_from_pixbuf(image_pixbuff)
        #     text = self.builder.get_object("result_text")
        #     text.set_text(remote_file.string)
        #     self.widget.add(FlowBoxChildWithData(result_item, remote_file))
        #
        # else:
        #     self.builder.add_objects_from_file(
        #         'ui/results_window.ui', ("result_image_only", ""))
        #     result_item = self.builder.get_object("result_image_only")
        #     result_item.set_from_pixbuf(image_pixbuff)
        #     flow_box = FlowBoxChildWithData(result_item, remote_file)
        #     flow_box.set_hexpand(False)
        #     style = flow_box.get_style_context()
        #     style.add_class("transparent")
        #     self.widget.set_homogeneous(False)
        #     self.widget.add(flow_box)


class ResultsHandler:

    def __init__(self, window: ResultsWindow, source):
        self.source: RemoteSource = source
        self.window = window
        self.pages: list[RemotePage] = []
        self.page_items: list[RemoteFile] = []
        self.selected_resources = []
        self.current_page = None
        self.activated_items = set()

    def get_current_page_index(self):
        current_index = 0
        for index, page in enumerate(self.pages):
            if self.current_page == page:
                current_index = index
        return current_index

    def view_image(self, widget, item):
        self.window.singleview.clear()
        self.window.singleview.show_view()
        self.window.singleview.show_previews(self.page_items, item.data)

    def results_single_item_selected(self, box: Gtk.FlowBox):
        selected_items = box.get_selected_children()
        # Somehow selected items sometimes is empty so this extra step
        for item in selected_items:
            self.window.singleview.show_file(item.data)
            self.source.file_selected(item.data)
            self.window.singleview.text.set_text(item.data.string.replace('_', ' '))
            break

    def results_selection_changed(self, box: Gtk.FlowBox):

        selected_items = box.get_selected_children()
        self.selected_resources.clear()

        for item in selected_items:
            self.selected_resources.append(item.data)
            self.activated_items.add(item)
            item.button.show()
        self.source.files_selection_changed(self.selected_resources)
        items_to_remove = []
        for item in self.activated_items:
            if item not in selected_items:
                item.button.hide()
                items_to_remove.append(item)
        for item in items_to_remove:
            self.activated_items.remove(item)

    def add_page(self, page):
        self.pages.append(page)
        first_page = len(self.pages) == 1
        self.window.multiview.show_view()
        if first_page:
            for file in page.get_page_content():
                self.add_page_item(file)
            self.current_page = page
            self.try_next_page(self.source, page_no=1)

    def clear(self):
        if self.page_items:
            self.window.multiview.clear()
        self.pages.clear()
        self.page_items.clear()
        self.current_page = None
        self.selected_resources.clear()

    def add_page_item(self, file: RemoteFile):
        self.window.multiview.add_item(file)
        self.page_items.append(file)

    def load_more_btn_clicked(self, widget):
        last_index = len(self.pages) - 1
        current_index = self.get_current_page_index()
        if current_index < last_index:
            next_page = self.pages[current_index + 1]
            for file in next_page.get_page_content():
                self.add_page_item(file)
            self.current_page = next_page

            # TODO: Make other faster implementations
            # Hide view button of any child ##Work around
            # But might be very slow
            def hide(child):
                if not child.is_selected():
                    child.button.hide()

            self.window.multiview.flow_box.foreach(hide)

            self.try_next_page(self.source, current_index + 1)
        elif current_index == last_index:
            self.try_next_page(self.source, current_index + 1)

    def scroll_edge_reached(self, *args, **kwargs):
        pass

    def try_next_page(self, source: RemoteSource, page_no):
        no_of_pages = len(self.pages)
        source.get_page(page_no)
        if len(self.pages) > no_of_pages:
            self.window.multiview.load_more_btn.show()
        else:
            self.window.multiview.load_more_btn.hide()
