import sys

from inkex.gui import asyncme
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW, SIZE_ASPECT_CROP
from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType

sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from remote import RemoteFile, RemotePage, RemoteSource
import json
from os.path import exists


class FAWindow(BasicWindow):
    name = "fa_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, scale=1,
                            grid_item_height=200,
                            grid_item_width=200,
                            padding=350)

        pix.enable_aspect = False
        pix.preview_scaling = 7
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
        return pix


class FAIcon(RemoteFile):
    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name'][:7]}-fontawesome"

    @property
    def thumbnail(self):
        name = self.name + ".svg"
        return self.remote.to_local_file(self.info["thumbnail"], name)

    def get_file(self):
        name = self.name + "file.svg"
        return self.remote.to_local_file(self.info["file"], name)


class FAPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source

    def get_page_content(self):
        for key, value in self.results:
            name =  "-".join(key.split("-")[:-1])
            category = key.split("-")[-1]
            url = f"https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/{category}/{name}.svg"
            info = {
                "id": name,
                "name": name,
                "author": url.split('/')[3],
                "thumbnail": url,
                "license": """The Font Awesome Free download is licensed under a Creative Commons
                    Attribution 4.0 International License and applies to all icons packaged
                    as SVG and JS file types.
                    """,
                "summary": "",
                "file": url,
            }

            yield FAIcon(self.remote_source, info)


class FASource(RemoteSource):
    name = 'Font Awesome Icons'
    desc = "Font Awesome is the Internet's icon library and toolkit, used by millions of designers, developers, and content creators."
    icon = "icons/font-awesome.png"
    file_cls = FAIcon
    page_cls = FAPage
    is_default = False
    is_enabled = True
    is_optimized = False
    options_window_width = 350
    items_per_page = 16
    window_cls = FAWindow

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)

        self.query = ""
        self.results = []
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Material Icons")
        self.options_window.set_option(
            "color", None, OptionType.COLOR, "Choose icon color")

        # -----------------------
        json = 'json/font-awesome.json'
        json_exists = exists(json)
        opt_json = 'json/font-awesome-optimized.json'
        optimized_json_exists = exists(opt_json)
        if optimized_json_exists:
            self.opt_icon_map = read_map_file(
                opt_json)
            self.is_optimized = True
        elif json_exists:
            self.icon_map = read_map_file(json)
        else:
            raise FileNotFoundError(
                "Cannot find any font awesome json files in json folder")

    def get_page(self, page_no: int):
        results = self.results[page_no *
                               self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            self.current_page = page_no
            page = FAPage(self, page_no, results)
            self.window.show_spinner()
            self.window.add_page(page)

    def search(self, query):
        self.results = []
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.results = [(key, value) for key, value in self.icon_map.items()
                        if key.startswith(query)]
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        # self.query = "a"
        # asyncme.run_or_none(self.search)("a")

    def on_change(self, options):
        self.query = options["query"]
        self.options = options
        if self.window and self.query:
            self.search(self.query)

def read_map_file(path):
    with open(path, mode='r') as f:
        m = json.load(f)
        f.close()
    return m
