import asyncio
import enum
import importlib
import inspect
import logging
import os
import sys
from abc import ABC
from asyncio import Queue
from threading import Thread

import requests
from cachecontrol import CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter
from gi.repository import Gtk, Gdk

from core.utils import asyncme
from sources.source_file import RemoteFile
from core.network.adapter import FileAdapter
from sources.source_page import RemotePage
from windows.basic_window import BasicWindow


class SourceType(enum.Enum):
    ICON = "icons"
    ILLUSTRATION = "illustration"
    FONT = "fonts"
    PHOTO = "photos"
    PALETTE = "color palette"


class RemoteSource(ABC):
    name = None
    desc = None
    icon = None
    source_type = None
    file_cls = RemoteFile
    page_cls = RemotePage
    is_default = False
    is_enabled = True
    items_per_page = 10
    options_window_width = 300
    window_cls = BasicWindow
    window: BasicWindow = None
    selected_files = []
    pix_manager = None

    sources = {}
    windows = []

    def __init_subclass__(cls):
        if not inspect.isabstract(cls) and cls.name:
            cls.sources[cls.__name__] = cls
            cls.windows.append(cls.window_cls)

    def __init__(self, cache_dir, import_manager) -> None:
        self.current_page = 0
        self.import_manager = import_manager
        self.options_window = None
        self.session = requests.session()
        self.cache_dir = cache_dir

        # asynchronous queue to process all background activities
        # by this source, assigned on attachment of source window
        self.task_queue = None
        self.task_loop = None

        self.session.mount(
            "https://",
            CacheControlAdapter(
                cache=FileCache(cache_dir),
                heuristic=ExpiresAfter(days=1),
            ),
        )
        self.session.mount('file://', FileAdapter())

    def get_page(self, page_no: int):
        """
        Adds specified page to window according to page_no
        page_no is 0 based
        Do Nothing if no other page exists
        """
        raise NotImplementedError(
            "You must implement a get_page function for this remote source!"
        )

    @asyncme.run_or_none
    def search(self, query):
        """
        Search for the given query and returns first page
        """
        raise NotImplementedError(
            "You must implement a search function for this remote source!"
        )

    def on_window_attached(self, window: BasicWindow, window_pane: Gtk.Paned):
        self.window = window

        # start async tasks queue in background thread
        self.task_queue: Queue = None
        self.task_loop = asyncio.new_event_loop()
        task_thread = Thread(target=self.start_background_loop, daemon=True)
        task_thread.start()
        while not self.task_loop.is_running():
            pass

    def start_background_loop(self) -> None:
        asyncio.set_event_loop(self.task_loop)
        self.task_queue = Queue()
        self.task_loop.run_until_complete(self.consume_task())

    def add_task_to_queue(self, fn, callback, *args, **kwargs):
        asyncio.run_coroutine_threadsafe(self.task_queue.put((fn, callback, args, kwargs)), loop=self.task_loop)

    async def consume_task(self):
        while True:
            fn, callback, args, kwargs = await self.task_queue.get()
            try:
                if inspect.iscoroutinefunction(fn):
                    result = await fn(*args, **kwargs)
                else:
                    result = fn(*args, **kwargs)
                callback(result=result, error=None)
            except Exception as err:
                callback(result=None, error=err)
            self.task_queue.task_done()

    def file_selected(self, file: RemoteFile):
        pass

    def file_saved(self, file: RemoteFile):
        self.import_manager.save_file(self, file)

    def files_selection_changed(self, files):
        self.selected_files = files
        self.import_manager.add_files(self, files)

    def __del__(self):
        self.session.close()

    def to_local_file(self, url, name, headers=None, content=False):
        """Get a remote url and turn it into a local file"""
        filepath = os.path.join(self.cache_dir, name)
        # if os.path.exists(filepath):
        #     return filepath
        remote = None
        if not headers:
            headers = {"User-Agent": "Inkscape"}
        try:
            remote = self.session.get(
                url, headers=headers
            )
            # self.session.close()
            # needs UserAgent otherwise many 403 or 429 for wiki commons
        except requests.exceptions.RequestException as err:
            return None
        except ConnectionError as err:
            return None
        except requests.exceptions.RequestsWarning:
            pass

        if remote and remote.status_code == 200:
            if content:
                return remote.content
            else:
                with open(filepath, "wb") as fhl:
                    # If we don't have data, return None (instead of empty file)
                    if fhl.write(remote.content):
                        return filepath
        return None

    @classmethod
    def load(cls, name):
        """Load the file or directory of remote sources"""
        if os.path.isfile(name):
            sys.path, sys_path = [os.path.dirname(name)] + sys.path, sys.path
            try:
                importlib.import_module(os.path.basename(name).rsplit(".", 1)[0])
            except ImportError:
                logging.error(f"Failed to load module: {name}")
            sys.path = sys_path
        elif os.path.isdir(name):
            for child in os.listdir(name):
                if not child.startswith("_") and child.endswith(".py"):
                    cls.load(os.path.join(name, child))

    @asyncme.mainloop_only
    def update_item(self, pic_path, item):
        css = self.pix_manager.style
        css = css.format(id=item.id, url=pic_path)
        item.style_prov.load_from_data(bytes(css, "utf8"))
        item.style_ctx.add_provider_for_screen(Gdk.Screen.get_default(), item.style_prov,
                                               Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # css_prov = Gtk.CssProvider()
        # css_prov.load_from_data(bytes(css, "utf8"))
        # item.style_ctx.remove_provider_for_screen(Gdk.Screen.get_default(), item.style_prov)
        # item.style_ctx.add_provider_for_screen(Gdk.Screen.get_default(), css_prov,
        #                                               Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # item.style_prov = css_prov

        # Fixme: Deleting item immediately here, makes it not appear
        # Wait for some signal from gtk before deleting
        # asyncme.run_or_none(os.remove)(pic_path)

    def fetch_and_update_multi_item(self, item):
        pass


def sanitize_query(query: str):
    return query.lower().strip().replace(' ', '%20')
