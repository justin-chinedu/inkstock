import os
from typing import Set

import gi
from inkex.gui import asyncme
from inkex.gui.window import ChildWindow
from utils.constants import CACHE_DIR
from remote import RemoteFile, RemotePage, RemoteSource
from utils.pixelmap import PixmapManager
from windows.view_change_listener import ViewChangeListener

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject


class ResultsWindow(ChildWindow):
    name = "results_window"

    def __init__(self, gapp):
        super().__init__(gapp)
        self.singleview = None
        self.multiview = None
        self.source = None
        self.handler: ResultsHandler = None

    @asyncme.mainloop_only
    def show_window(self, window, name):
        page_stack: Gtk.Stack = self.window

        def remove(child: Gtk.Widget):
            page_stack.remove(child)

        page_stack.foreach(remove)
        if not page_stack.get_child_by_name(name):
            page_stack.add_named(window, name)
        child = page_stack.get_child_by_name(name)
        if page_stack.get_visible_child() != child:
            page_stack.set_visible_child(child)
            if isinstance(self.source, ViewChangeListener):
                self.source.on_view_changed(child)

    def refresh_window(self):
        if self.is_multi_view():
            self.multiview.clear()
            items = self.handler.page_items
            for item in items:
                self.multiview.add_item(item)
        else:
            item = self.singleview.selected_child.data
            self.singleview.clear()
            self.singleview.show_previews(self.handler.page_items, item)

    def init(self, parent=None, **kwargs):
        self.source = kwargs["source"]
        self.handler = ResultsHandler(self, self.source)
        self.w_tree.connect_signals(self.handler)
        super().init(parent, **kwargs)

    def load_widgets(self, *args, **kwargs):
        pixmaps = kwargs.get("pixmaps", None)
        if not pixmaps:
            pixmaps = PixmapManager(CACHE_DIR)
        self.multiview = MultiItemView(self, pixmaps)
        self.singleview = SingleItemView(self, pixmaps)

    def is_multi_view(self) -> bool:
        if self.window.get_visible_child_name().startswith("multiview"):
            return True
        else:
            return False

    def get_multi_view_displayed_data(self, only_selected=True):
        # if self.is_multi_view():
        if only_selected:
            return self.multiview.flow_box.get_selected_children()
        return self.multiview.flow_box.get_children()


class FlowBoxChildWithData(Gtk.FlowBoxChild):
    def __init__(self, data, show_text=True):
        super().__init__()
        self.id = None
        self.pic_path = None
        self.data = data
        builder = Gtk.Builder()
        builder.add_objects_from_file(
            'ui/results_window.ui', ["view_image_btn", "view_icon", "result_item"])
        self.button: Gtk.Button = builder.get_object("view_image_btn")
        self.label: Gtk.Label = builder.get_object("result_text")
        self.image: Gtk.Widget = builder.get_object("result_image")
        self.result = builder.get_object("result_item")
        self.style_ctx: Gtk.StyleContext = self.result.get_style_context()
        self.style_prov = None
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
        self.list.set_focus_on_click(True)
        self.scroll: Gtk.ScrolledWindow = self.builder.get_object("results_single_scroll_previews")
        self.back_btn: Gtk.Button = self.builder.get_object("results_single_back")
        self.back_btn.connect("clicked", lambda btn: self.window.multiview.show_view())
        self.builder.connect_signals(window.handler)
        self.single_view.show()

    @asyncme.mainloop_only
    def clear(self):
        def remove(child: Gtk.Widget):
            child.destroy()

        self.list.foreach(remove)

    def show_view(self):
        self.window.show_window(self.single_view, "singleview" + str(id(self)))

    @asyncme.mainloop_only
    def show_previews(self, remote_files, selected_file):
        self.selected_child = None
        self.children = {}
        self.length = len(remote_files)
        self.index = 0
        self.list.set_min_children_per_line(self.length)
        self.children.clear()

        for index, remote_file in enumerate(remote_files):
            self.pixmaps.get_pixbuf_for_type(remote_file, "thumb", self.callback, index, remote_file, selected_file)
            # self.pixmaps.get_pixbuf_for_thumbnails((remote_file, index), selected_file, self.callback)

    @asyncme.mainloop_only
    def add_children(self):
        self.clear()
        selected_index = 0
        for i in range(0, self.length):
            child = self.children[i]
            self.list.add(child)
            if child == self.selected_child:
                selected_index = i
        # FIXME: Doesn't work : scrolling to selected item
        adj = self.scroll.get_hadjustment()
        val = adj.get_upper() * ((selected_index + 1) / self.length)
        self.scroll.get_hadjustment().set_value(val)
        # self.list.set_focus_hadjustment(adj)
        self.list.select_child(self.selected_child)
        # self.selected_child.grab_focus()

    def show_file(self, file):
        self.pixmaps.get_pixbuf_for_type(file, "single", self.set_image)

    def set_image(self, pixbuf):
        self.image.set_from_pixbuf(pixbuf)

    @asyncme.mainloop_only
    def callback(self, pic_path, index, remote_file, selected_file):
        item_id = "id_single" + str(remote_file.id)
        css = self.pixmaps.style
        css = css.format(id=item_id, url=pic_path)

        child = FlowBoxChildWithData(remote_file)
        child.id = item_id
        child.set_size_request(self.pixmaps.preview_item_width, self.pixmaps.preview_item_height)
        child.set_hexpand(False)
        child.set_vexpand(False)
        child.label.hide()
        child.style_ctx.add_class(item_id)
        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(bytes(css, "utf8"))
        child.style_prov = css_prov
        child.style_ctx.add_provider_for_screen(Gdk.Screen.get_default(), css_prov,
                                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # asyncme.run_or_none(os.remove)(pic_path)
        self.children[index] = child
        self.index += 1

        if remote_file.id == selected_file.id:
            self.selected_child = child

        if self.index == self.length:
            self.add_children()


class MultiItemView:
    def __init__(self, window: ResultsWindow, pixmaps) -> None:
        self.builder = Gtk.Builder()
        self.pixmaps = pixmaps
        self.window = window
        self.opened_item = None
        self.builder.add_objects_from_file(
            'ui/results_window.ui', ["results_multi_view"])
        self.multi_view = self.builder.get_object("results_multi_view")
        self.flow_box: Gtk.FlowBox = self.builder.get_object("results_flow")
        self.load_more_btn = self.builder.get_object("load_more_btn")
        self.builder.connect_signals(window.handler)
        self.multi_view.show()
        self.index = 0
        self.children = {}

    @asyncme.mainloop_only
    def clear(self):
        def remove(child: Gtk.Widget):
            child.destroy()

        self.flow_box.foreach(remove)

    def show_view(self):
        self.window.show_window(self.multi_view, "multiview" + str(id(self)))

    def add_item(self, remote_file: RemoteFile):
        self.pixmaps.get_pixbuf_for_type(remote_file, "multi", self.callback, remote_file)

    @asyncme.mainloop_only
    def callback(self, pic_path, remote_file):
        item_id = "id_multi" + str(remote_file.id)
        css = self.pixmaps.style
        css = css.format(id=item_id, url=pic_path)

        child = FlowBoxChildWithData(remote_file)
        child.id = item_id
        child.pic_path = pic_path
        child.result.set_size_request(self.pixmaps.grid_item_width, self.pixmaps.grid_item_height)
        child.style_ctx.add_class(item_id)

        if remote_file.string and remote_file.show_name:
            child.label.set_text(remote_file.string)
        else:
            child.label.hide()
        # child.set_name(item_id)
        child.button.connect("clicked", self.window.handler.view_image, child)
        child.button.hide()
        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(bytes(css, "utf8"))
        child.style_prov = css_prov
        child.style_ctx.add_provider_for_screen(Gdk.Screen.get_default(), css_prov,
                                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.flow_box.add(child)
        # asyncme.run_or_none(os.remove)(pic_path)
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
        self.window.multiview.opened_item = item
        self.window.singleview.clear()
        self.window.singleview.show_view()
        self.window.singleview.show_previews(self.page_items, item.data)

    def results_single_item_selected(self, box: Gtk.FlowBox):
        """Called when an item is selected in from flow box in single view """
        selected_items = box.get_selected_children()
        # Somehow selected items sometimes is empty so this extra step
        for item in selected_items:
            self.window.singleview.show_file(item.data)
            self.window.singleview.text.set_text(item.data.string.replace('_', ' '))
            self.source.file_selected(item.data)
            break

    def results_selection_changed(self, box: Gtk.FlowBox):

        selected_items = box.get_selected_children()
        self.selected_resources.clear()
        selected_item = None
        for item in selected_items:
            self.selected_resources.append(item.data)
            self.activated_items.add(item)
            item.button.show()
            item.label.hide()
            if len(selected_items) == 1:
                selected_item = item.data

        items_to_remove = []
        for item in self.activated_items:
            if item not in selected_items:
                item.button.hide()
                item.label.show()
                items_to_remove.append(item)
        for item in items_to_remove:
            self.activated_items.remove(item)

        self.source.files_selection_changed(self.selected_resources)
        if selected_item:
            self.source.file_selected(selected_item)

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
        print("clearing items........")
        self.source.files_selection_changed(self.selected_resources)

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

    def previous_btn_clicked(self, btn):
        children = self.window.singleview.list.get_children()
        selected = self.window.singleview.list.get_selected_children()[0]
        for index, child in enumerate(children):
            if child == selected and not index == 0:
                self.window.singleview.list.select_child(children[index - 1])
                break
        pass

    def next_btn_clicked(self, btn):
        children = self.window.singleview.list.get_children()
        selected_children = self.window.singleview.list.get_selected_children()
        if not selected_children: return  # if children not yet loaded( due to size ) we just return
        first_selected = selected_children[0]
        for index, child in enumerate(children):
            if child == first_selected and not index >= len(children) - 1:
                self.window.singleview.list.select_child(children[index + 1])
                break

    def scroll_edge_reached(self, *args, **kwargs):
        pass

    def try_next_page(self, source: RemoteSource, page_no):
        no_of_pages = len(self.pages)
        source.get_page(page_no)
        if len(self.pages) > no_of_pages:
            self.window.multiview.load_more_btn.show()
        else:
            self.window.multiview.load_more_btn.hide()
