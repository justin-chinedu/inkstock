import json
import sys

from inkex.gui import asyncme
from tasks.svg_color_replace import SvgColorReplace
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW

from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType, ChangeReciever

sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from remote import RemoteFile, RemotePage, RemoteSource


class UndrawWindow(BasicWindow):
    name = "undraw_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        return self.source.pix_manager


class UndrawIllustration(RemoteFile):

    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name']}-undraw"

    def get_thumbnail(self):
        name = self.name + ".svg"
        return self.remote.to_local_file(self.info["thumbnail"], name)

    def get_file(self):
        name = self.name + "file.svg"
        return self.remote.to_local_file(self.info["file"], name)


class UndrawPage(RemotePage, ChangeReciever):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source

    def get_page_content(self):
        for result in self.results:
            yield UndrawIllustration(self.remote_source, result)


class Undraw(RemoteSource):
    name = "Undraw"
    desc = "Open-source illustrations for any idea you can imagine and create."
    icon = "icons/undraw.png"
    file_cls = UndrawIllustration
    page_cls = UndrawPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    reqUrl = "https://undraw.co/api/search"
    window_cls = UndrawWindow

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)
        self.query = ""
        self.pix_manager = self.setup_pixmanager()
        self.results = []
        self.options = {"dominant_color": None}
        self.color_ext = SvgColorReplace()
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search unDraw")
        self.options_window.set_option(
            "dominant_color", None, OptionType.COLOR, "Choose dominant color")

    def setup_pixmanager(self):
        pix = PixmapManager(CACHE_DIR, pref_width=200,
                            pref_height=200, scale=1,
                            grid_item_height=250,
                            grid_item_width=250,
                            padding=20,
                            aspect_ratio=SIZE_ASPECT_GROW)
        pix.style = """.{id}{{
            background-color: white;
            background-size: contain;
            background-repeat: no-repeat;
            border-radius: 5%;
            background-origin: content-box;
            background-image: url("{url}");
            }}
            
            window flowbox > flowboxchild {{
            border-radius: 5%;
            }}
        """
        pix.single_preview_scale = 0.7
        return pix

    def get_page(self, page_no: int):
        self.current_page = page_no
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            page = UndrawPage(self, page_no, results)
            self.window.add_page(page)

    def search(self, query, tags=...):
        self.results = []
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        headersList = {
            "Accept": "*/*",
            "User-Agent": "Inkscape",
            "Content-Type": "application/json"
        }

        payload = json.dumps({"query": query})
        try:
            response = self.session.request("POST", self.reqUrl, data=payload, headers=headersList)
            illus = response.json()["illos"]
            for item in illus:
                result = {
                    "thumbnail": item["image"],
                    "file": item["image"],
                    "name": item["title"],
                    "license": ""
                }
                self.results.append(result)
            self.get_page(0)
        except:
            print("There was an error trying to fetch content")

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.query = "acc"
        asyncme.run_or_none(self.search)(self.query)
        # self.window.show_options_window(self.options_window.window, self)

    def on_change(self, options):

        self.options = options
        if self.window and self.query and self.query != options["query"]:
            self.query = options["query"]
            self.search(self.query)
            return
        color = None
        if "dominant_color" in self.options:
            color = self.options["dominant_color"]
        if self.window and color:
            items = self.window.results.get_multi_view_displayed_data(only_selected=True)
            self.change_items_color(color, items)

    @asyncme.run_or_none
    def change_items_color(self, color, items):
        old_color = "#6c63ff"
        self.color_ext.is_active = True
        self.color_ext.new_fill_colors[old_color] = color
        for item in items:
            thumbnail = item.data.get_thumbnail()
            thumbnail = self.color_ext.do_task(thumbnail)
            thumbnail = self.pix_manager.get_pixbuf_for_task(thumbnail)
            self.update_item(thumbnail, item)
