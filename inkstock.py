import os

from core.gui.app import GtkApp
from sources.remote import RemoteSource
from windows.import_window import ImportWindow, ImportResults
from windows.inkstocks_window import InkStockWindow
from windows.results_window import ResultsWindow
from gi.repository import Gtk, GLib


class InkStockApp(GtkApp):
    """Base App
    Add all windows to windows for it to be recognised"""
    app_name = "InkStock"
    ui_dir = "ui"
    windows = []

    def __init__(self, start_loop=False, start_gui=True, **kwargs):
        self.ext = kwargs.setdefault("ext", None)
        RemoteSource.load(os.path.join(os.path.dirname(__file__), 'sources'))
        self.windows = RemoteSource.windows
        self.windows.insert(0, InkStockWindow)
        self.windows.insert(0, ResultsWindow)
        self.windows.insert(0, ImportWindow)
        self.windows.insert(0, ImportResults)

        super().__init__(start_loop, start_gui, **kwargs)


if __name__ == '__main__':
    InkStockApp(start_loop=True)
