from gi.repository import Gtk, Gdk

from inkex.gui import ChildWindow, asyncme
from remote import RemoteFile
from windows.basic_window import BasicWindow


class ImportWindow(BasicWindow):
    """Basic window for Import manager"""
    name = "import_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        self.manager = None
        self.results = None
        super().__init__(gapp)

    def load_widgets(self, *args, **kwargs):
        """Retrieves manager from args.
        Sets the pane's  width
        Assigns this window to manager
        Creates and displays the import result window"""
        self.manager = kwargs["manager"]
        self.widget("basic_paned").set_position(300)
        self.show_options_window(self.manager.options_window.window, self.manager)
        self.manager.window = self
        if not self.results:
            self.results: ImportResults = self.gapp.load_window("import_results_window", manager=self.manager)
        self.show_window(self.results, "import_results")


class ImportItem(Gtk.FlowBoxChild):
    def __init__(self, data, show_text=True):
        super().__init__()
        self.id = None
        self.pic_path = None
        self.data = data
        builder = Gtk.Builder()
        builder.add_objects_from_file(
            'ui/results_window.ui', ["import_item"])
        self.cancel: Gtk.Button = builder.get_object("import_cancel")
        self.result = builder.get_object("import_item")
        self.style_ctx: Gtk.StyleContext = self.result.get_style_context()
        self.style_prov = None
        self.add(self.result)
        self.show()


class ImportResults(ChildWindow):
    # name of window
    name = "import_results_window"

    def __init__(self, gapp):
        # name of ui file
        self.name = "results_window"

        self.builder = Gtk.Builder()
        self.builder.add_objects_from_file(
            'ui/results_window.ui', ["results_multi_view"])
        self.multi_view = self.builder.get_object("results_multi_view")
        self.flow_box: Gtk.FlowBox = self.builder.get_object("results_flow")
        self.handler = None
        self.manager = None
        self.multi_view.show()
        super().__init__(gapp)

    @asyncme.mainloop_only
    def show_window(self, window, name):
        page_stack: Gtk.Stack = self.window

        def remove(page_child: Gtk.Widget):
            page_stack.remove(page_child)

        page_stack.foreach(remove)
        if not page_stack.get_child_by_name(name):
            page_stack.add_named(window, name)
        child = page_stack.get_child_by_name(name)
        if page_stack.get_visible_child() != child:
            page_stack.set_visible_child(child)

    def init(self, parent=None, **kwargs):
        self.manager = kwargs.pop("manager")
        self.handler = ImportHandler(self, self.manager)
        self.w_tree.connect_signals(self.handler)
        super().init(parent, **kwargs)

    def load_widgets(self):
        self.show_window(self.multi_view, "multiview" + str(id(self)))

    @asyncme.mainloop_only
    def remove_item(self, item: ImportItem):
        self.flow_box.remove(item)

    @asyncme.mainloop_only
    def clear(self):
        def remove(child: Gtk.Widget):
            child.destroy()

        self.flow_box.foreach(remove)

    def add_items(self, remote_files: list[RemoteFile], source_pixmap):
        for remote_file in remote_files:
            source_pixmap.get_pixbuf_for_type(remote_file, "multi", self.callback, remote_file, source_pixmap)

    @asyncme.mainloop_only
    def callback(self, pic_path, remote_file, pixmap):
        item_id = "id_multi" + str(remote_file.id)
        css = pixmap.style
        css = css.format(id=item_id, url=pic_path)

        child = ImportItem(remote_file)
        child.id = item_id
        child.pic_path = pic_path
        child.result.set_size_request(pixmap.grid_item_width, pixmap.grid_item_height)
        child.style_ctx.add_class(item_id)

        child.cancel.connect("clicked", self.manager.remove_source, child)

        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(bytes(css, "utf8"))
        child.style_prov = css_prov
        child.style_ctx.add_provider_for_screen(Gdk.Screen.get_default(), css_prov,
                                                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.flow_box.add(child)
        self.flow_box.select_child(child)


class ImportHandler:
    # Doesn't do anything yet
    def __init__(self, window, manager):
        self.manager = manager
        self.window: ImportResults = window

    def results_selection_changed(self, box: Gtk.FlowBox): pass

    def load_more_btn_clicked(self, widget): pass

    def previous_btn_clicked(self, btn): pass

    def next_btn_clicked(self, btn): pass

    def results_single_item_selected(self, box: Gtk.FlowBox): pass
