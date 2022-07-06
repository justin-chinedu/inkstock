import enum
import importlib
import inspect
import logging
import os
import sys
from abc import ABC

import requests
from cachecontrol import CacheControlAdapter
from cachecontrol.caches.file_cache import FileCache
from cachecontrol.heuristics import ExpiresAfter
from gi.repository import Gtk, Gdk

from inkex.gui import asyncme
from tasks.task import Task
from windows.basic_window import BasicWindow

LICENSE_ICONS = os.path.join(os.path.dirname(__file__), 'licenses')

LICENSES = {
    "cc-0": {
        "name": "CC0",
        "modules": ["nocopyright"],
        "url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "overlay": "cc0.svg",
    },
    "cc-by-3.0": {
        "name": "CC-BY 3.0 Unported",
        "modules": ["by"],
        "url": "https://creativecommons.org/licenses/by/3.0/",
        "overlay": "cc-by.svg",
    },
    "cc-by-4.0": {
        "name": "CC-BY 4.0 Unported",
        "modules": ["by"],
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "overlay": "cc-by.svg",
    },
    "cc-by-sa-4.0": {
        "name": "CC-BY SA 4.0",
        "modules": ["by", "sa"],
        "url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "overlay": "cc-by-sa.svg",
    },
    "cc-by-sa-3.0": {
        "name": "CC-BY SA 3.0",
        "modules": ["by", "sa"],
        "url": "https://creativecommons.org/licenses/by-sa/3.0/",
        "overlay": "cc-by-sa.svg",
    },
    "cc-by-nc-sa-4.0": {
        "name": "CC-BY NC SA 4.0",
        "modules": ["by", "sa", "nc"],
        "url": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
        "overlay": "cc-by-nc-sa.svg",
    },
    "cc-by-nc-sa-3.0": {
        "name": "CC-BY NC SA 3.0",
        "modules": ["by", "sa", "nc"],
        "url": "https://creativecommons.org/licenses/by-nc-sa/3.0/",
        "overlay": "cc-by-nc-sa.svg",
    },
    "cc-by-nc-3.0": {
        "name": "CC-BY NC 3.0",
        "modules": ["by", "nc"],
        "url": "https://creativecommons.org/licenses/by-nc/3.0/",
        "overlay": "cc-by-nc.svg",
    },
    "cc-by-nd-3.0": {
        "name": "CC-BY ND 3.0",
        "modules": ["by", "nd"],
        "url": "https://creativecommons.org/licenses/by-nd/3.0/",
        "overlay": "cc-by-nd.svg",
    },
    "gpl-2": {
        "name": "GPLv2",
        "modules": ["retaincopyrightnotice", "sa"],
        "url": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt",
        "overlay": "gpl.svg",
    },
    "gpl-3": {
        "name": "GPLv3",
        "modules": ["retaincopyrightnotice", "sa"],
        "url": "https://www.gnu.org/licenses/gpl-3.0.txt",
        "overlay": "gpl.svg",
    },
    "agpl-3": {
        "name": "AGPLv3",
        "modules": ["retaincopyrightnotice", "sa"],
        "url": "https://www.gnu.org/licenses/agpl-3.0.txt",
        "overlay": "gpl.svg",
    },
    "mit": {
        "name": "MIT",
        "modules": ["retaincopyrightnotice"],
        "url": "https://mit-license.org/",
        "overlay": "mit.svg",
    },
    "asl": {
        "name": "Apache License",
        "modules": ["retaincopyrightnotice"],
        "url": "https://www.apache.org/licenses/LICENSE-2.0.txt",
        "overlay": "asl.svg",
    },
    "bsd": {
        "name": "BSD",
        "modules": ["retaincopyrightnotice", "noendorsement"],
        "url": "https://opensource.org/licenses/BSD-3-Clause",
        "overlay": "bsd.svg",
    },
}


class RemoteFile:
    def get_thumbnail(self):
        return self.remote.to_local_file(self.info["thumbnail"], self.file_name)

    def get_file(self):
        return self.info["file"]

    def __init__(self, remote, info):
        # name to be displayed
        self.name = None
        # name to be saved as including extension
        self.file_name = None
        for field in ("name", "thumbnail", "license", "file"):
            if field not in info:
                raise ValueError(f"Field {field} not provided in RemoteFile package")
        self.info = info
        self.id = hash(self.info["file"])
        self.remote: RemoteSource = remote
        self.tasks: list[Task] = []
        self.show_name = False

    @property
    def string(self):
        return self.info["name"]

    @property
    def license(self):
        return self.info["license"]

    @property
    def license_info(self):
        return LICENSES.get(self.license, {
            "name": "Unknown",
            "url": self.info.get("descriptionurl", ""),
            "modules": [],
            "overlay": "unknown.svg",
        })

    @property
    def author(self):
        return self.info["author"]


class RemotePage:

    def __init__(self, remote_source, page_no: int):
        self.page_no = page_no
        self.remote_source = remote_source

    def get_page_content(self):
        """Should be implemented
            Simply yields a list of remotefiles
        """
        raise NotImplementedError(
            "You must implement a search function for this remote source!"
        )


class SourceType(enum.Enum):
    ICON = "icons"
    ILLUSTRATION = "illustration"
    FONT = "fonts"
    PHOTO = "photos"
    SWATCH = "swatches"


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
        if not inspect.isabstract(cls):
            cls.sources[cls.__name__] = cls
            cls.windows.append(cls.window_cls)

    def __init__(self, cache_dir, dm) -> None:
        self.current_page = 0
        self.dm = dm
        self.options_window = None
        self.session = requests.session()
        self.cache_dir = cache_dir
        self.session.mount(
            "https://",
            CacheControlAdapter(
                cache=FileCache(cache_dir),
                heuristic=ExpiresAfter(days=1),
            ),
        )

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

    def file_selected(self, file: RemoteFile):
        pass

    def files_selection_changed(self, files):
        self.selected_files = files
        self.dm.add_files(self, files)

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
    return query.lower().replace(' ', '_')
