from core.constants import CACHE_DIR
from core.utils import asyncme
from core.gui.window import ChildWindow
from gi.repository import Gtk

from core.gui.pixmap_manager import PixmapManager


class BasicWindow(ChildWindow):
    name = "basic_window"

    def __init__(self, gapp):
        self.source = None
        from windows.results_window import ResultsWindow
        self.results: ResultsWindow = None
        super().__init__(gapp)
        self.home_window = self.widget(self.name)
        self.spinner = self.widget("basic_spinner")

    def load_widgets(self, *args, **kwargs):
        if not self.source:
            self.source = kwargs["source"]
        self.widget("basic_paned").set_position(self.source.options_window_width)
        if self.source.options_window:
            self.show_options_window(self.source.options_window.window, self.source)
        self.source.on_window_attached(self, self.widget("basic_paned"))

    def get_pixmaps(self):
        """Retrieves the pixel map manager for the results window
        Custom windows should override to customize manager properties"""
        results_pixmanager = PixmapManager(CACHE_DIR)
        return results_pixmanager

    @asyncme.mainloop_only
    def show_window(self, window, name):
        """Adds home window and result window to the page stack
        Custom Windows should override this method to customize location of results window
        """
        page_stack: Gtk.Stack = self.widget("basic_window_stack")

        def remove(child: Gtk.Widget):
            page_stack.remove(child)
            # child.unparent()

        page_stack.foreach(remove)
        name = window.name + name
        if not page_stack.get_child_by_name(name):
            page_stack.add_named(window.window, name)
        child = page_stack.get_child_by_name(name)
        if page_stack.get_visible_child() != child:
            page_stack.set_visible_child(child)

    def show_options_window(self, window, source):

        options_page_stack: Gtk.Stack = self.widget("basic_options_stack")
        name = "options" + str(id(source))
        if not options_page_stack.get_child_by_name(name):
            options_page_stack.add_named(window, name)
        child = options_page_stack.get_child_by_name(name)

        if options_page_stack.get_visible_child() != child:
            options_page_stack.set_visible_child(child)

    @asyncme.mainloop_only
    def show_spinner(self):
        self.spinner.show()
        page_stack: Gtk.Stack = self.widget("basic_window_stack")
        if not page_stack.get_child_by_name("spinner"):
            page_stack.add_named(self.spinner, "spinner")
        child = page_stack.get_child_by_name("spinner")
        if page_stack.get_visible_child() != child:
            page_stack.set_visible_child(child)

    @asyncme.mainloop_only
    def add_page(self, page):
        if not self.results:
            source = self.source
            self.results = self.gapp.load_window("results_window", pixmaps=self.get_pixmaps(), source=source)
        self.show_window(self.results, self.source.name)
        self.results.handler.add_page(page)

    @asyncme.mainloop_only
    def clear_pages(self):
        if self.results:
            self.results.handler.clear()
