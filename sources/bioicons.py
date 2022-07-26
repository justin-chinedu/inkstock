import os
from datetime import datetime
from os.path import exists

import requests
from cachecontrol import CacheControlAdapter
from cachecontrol.caches import FileCache
from cachecontrol.heuristics import ExpiresAfter

from core.utils import asyncme
from sources.source import RemoteSource, sanitize_query, SourceType
from sources.source_page import RemotePage, NoResultsPage
from sources.source_file import RemoteFile
from sources.svg_source import SvgSource
from core.constants import CACHE_DIR, LICENSES
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType


class BioWindow(BasicWindow):
    name = "bio_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmap_manager(self):
        pix = PixmapManager(CACHE_DIR, scale=3,
                            grid_item_height=220,
                            grid_item_width=220,
                            padding=120)

        pix.enable_aspect = False
        pix.preview_scaling = 1
        pix.preview_padding = 30
        pix.preview_aspect_ratio = SIZE_ASPECT_GROW
        pix.preview_item_height = 100
        pix.preview_item_width = 100
        pix.style = """.{id}{{
            background-color: white;
            background-size: contain;
            background-repeat: no-repeat;
            background-origin: content-box;
            background-image: url("{url}");
            }}
        """
        self.source.pix_manager = pix
        return pix


class BioIcon(RemoteFile):
    def __init__(self, source, info):
        super().__init__(source, info)
        self.name = f"{self.info['name']}-bio"
        self.file_name = self.name + ".svg"
        self.show_name = True


class BioIconsPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source

    def get_page_content(self):
        for result in self.results:
            info = {
                "name": result["name"],
                "summary": result["category"],
                "created": None,
                "popularity": 0,
                "author": result["author"],
                "thumbnail": f"{self.remote_source.icon_url}{result['license']}/{result['category']}/{result['author']}/{result['name']}.svg".replace(" ", "_"),
                "file": f"{self.remote_source.icon_url}{result['license']}/{result['category']}/{result['author']}/{result['name']}.svg".replace(" ", "_"),
                "license": result["license"],
            }

            icon = BioIcon(self.remote_source, info)
            yield icon


class BioIconsSource(RemoteSource):
    name = 'Bio Icons'
    desc = "Bioicons is a free library of open source icons for " \
           "scientific illustrations using vector graphics software such as " \
           "Inkscape or Adobe Illustrator."
    icon = "icons/bioicons.svg"
    source_type = SourceType.ILLUSTRATION
    file_cls = BioIcon
    page_cls = BioIconsPage
    is_default = False
    is_enabled = True
    options_window_width = 300
    items_per_page = 16
    window_cls = BioWindow

    db_url = "https://bioicons.com/icons/icons.json"
    icon_url = "https://bioicons.com/icons/"

    def __init__(self, cache_dir, import_manager):
        super().__init__(cache_dir, import_manager)

        self.query = ""
        self.results = []
        self.json_path = None
        self.icon_map = None
        self.category = ""
        self._json = None
        self.session.mount(
            "https://",
            CacheControlAdapter(
                cache=FileCache(cache_dir),
                heuristic=ExpiresAfter(days=5),
            ),
        )
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, f"Search {self.name}")

    def get_page(self, page_no: int):
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            self.current_page = page_no
            page = BioIconsPage(self, page_no, results)
            self.window.add_page(page)

    @asyncme.run_or_none
    def get_home(self):
        self.window.clear_pages()
        self.window.show_spinner()
        # check if local db is up-to-date with Last Modified header
        try:
            response = requests.head(self.db_url)
        except Exception:
            response = None

        self.json_path = os.path.join(self.cache_dir, "bio_icons.json")
        if not os.path.isfile(self.json_path):
            last_modified = 0
        else:
            last_modified = os.path.getmtime(self.json_path)

        if response is not None:
            last_update = datetime.strptime(
                response.headers["Last-Modified"], "%a, %d %b %Y %H:%M:%S GMT"
            ).timestamp()
            # if icon db was modified download new database
            if last_modified < last_update:
                self.to_local_file(self.db_url, name="bio_icons.json")
        self.load_icon_map()
        categories = set([icon["category"].replace("_", " ") for icon in self.icon_map])
        categories = sorted(list(categories))
        self.show_categories(categories)
        self.search("")

    @asyncme.mainloop_only
    def show_categories(self, categories: list):
        select_option = self.options_window.set_option("category",
                                                       categories,
                                                       OptionType.SELECT,
                                                       show_separator=False, attach=False)
        self.options_window.set_option("category_grp", [select_option], OptionType.GROUP, "Select Category")
        self.options_window.set_option("info", "", OptionType.TEXTVIEW, show_separator=False)

    @asyncme.run_or_none
    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.window.show_spinner()
        if query:
            self.results = [icon for icon in self.icon_map
                            if query in icon["name"] and self.category in icon["category"]]
        else:
            self.results = [icon for icon in self.icon_map if self.category in icon["category"]]

        if not self.results:
            self.window.add_page(NoResultsPage(query))
        else:
            self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.get_home()

    def on_change(self, options):
        if not self.window:
            return

        query = sanitize_query(options["query"])
        if options.get("category"):
            self.category = options.get("category").replace(" ", "_")
        else:
            self.category = ""
        self.query = query
        self.options = options
        self.search(self.query)
        return

    def load_icon_map(self):
        # -----------------------
        if self.json_path:
            json_exists = exists(self.json_path)
            if json_exists:
                self.icon_map = SvgSource.read_map_file(self.json_path)
        # ---------

    def file_selected(self, file: RemoteFile):
        super().file_selected(file)
        info = file.info
        text = f'<span  size="large" weight="normal" >Illustration by</span>\n\n' + \
               f'<span  size="large" weight="bold" >{info["author"]}</span>\n\n' + \
               f'<span  size="medium" weight="normal" >Available under the {LICENSES[info["license"]]["name"]} license, ' \
               f'<a href="{LICENSES[info["license"]]["url"] }">More Info</a></span>'
        text.replace("&", "&amp;")
        self.options_window.options["info"].view.set_markup(text)
