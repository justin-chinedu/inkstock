from remote import RemoteFile, RemotePage, RemoteSource
import json
import sys
from utils.constants import CACHE_DIR
from inkex.gui.pixmap import PadFilter, PixmapManager, SizeFilter

from windows.basic_window import BasicWindow
from windows.options_window import ChangeReciever, OptionType, OptionsWindow


class PexelsWindow(BasicWindow, ChangeReciever):
    name = "pexels_window"

    def __init__(self, gapp):
        # name of the widget file and id 
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        return PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1)


class PexelsFile(RemoteFile):
    def __init__(self, remote, info, headers):
        super().__init__(remote, info)
        self.headers = headers
        self.name = f"{self.info['name'][:7]}-{self.info['id']}-pexels"

    @property
    def thumbnail(self):
        name = self.name + ".png"
        return self.remote.to_local_file(self.info["thumbnail"], name, self.headers)

    def get_file(self):
        name = self.name + "file.png"
        return self.remote.to_local_file(self.info["file"], name, self.headers)


class PexelsPage(RemotePage):
    def __init__(self, remote_source, page_no: int, query):
        super().__init__(remote_source, page_no)
        self.query = query

    def get_page_content(self):
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "Inkscape",
            "Content-Type": "application/json",
            "Authorization": "563492ad6f917000010000016afb431a4e284b808cfc571ba347c4eb"
        }

        params = {}
        if self.query:
            params["query"] = self.query
        params["orientation"] = self.remote_source.options["orientation"]
        params["size"] = self.remote_source.options["size"]

        if self.remote_source.options.get("color", None):
            params["color"] = self.remote_source.options["color"]

        params["per_page"] = self.remote_source.items_per_page
        params["page"] = self.page_no + 1

        try:
            response = self.remote_source.session.request(
                "GET", self.remote_source.reqUrl, params=params, headers=headers_list)
            photos = []
            for photo in response.json()["photos"]:
                info = {
                    "id": photo["id"],
                    "width": photo["width"],
                    "height": photo["height"],
                    "url": photo["url"],
                    "photographer": photo["photographer"],
                    "photographer_url": photo["photographer_url"],
                    "photographer_id": photo["photographer_id"],
                    "avg_color": photo["avg_color"],
                    "thumbnail": photo["src"]["tiny"],
                    "file": photo["src"][self.remote_source.options["size"]],
                    "name": photo["alt"],
                    "license": ""
                }

                photos.append(PexelsFile(self.remote_source, info, headers_list))
            return photos
        except:
            print("Error trying to establish connection")


class Pexels(RemoteSource, ChangeReciever):
    name = "Pexels"
    desc = "Pexels is a provider of stock photography and stock footage. It was founded in Germany in 2014 and " \
           "maintains a library with over 3.2 million free stock photos and videos. "
    icon = "icons/pexels.png"
    file_cls = PexelsFile
    page_cls = PexelsPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    reqUrl = "https://api.pexels.com/v1/search"
    window_cls = PexelsWindow

    def __init__(self, cache_dir) -> None:
        super().__init__(cache_dir)
        self.query = ""
        # setting defaults
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Pexels")
        self.options_window.set_option("orientation", [
            "landscape", "portrait", "square"], OptionType.DROPDOWN, "Choose orientation")
        self.options_window.set_option(
            "size", ["large", "medium", "small"], OptionType.DROPDOWN, "Choose size of photo")
        self.options_window.set_option(
            "color", None, OptionType.COLOR, "Choose preferred color")

    def get_page(self, page_no: int):
        self.current_page = page_no
        page = PexelsPage(self, self.current_page, self.query)
        self.window.add_page(page)

    def search(self, query, tags=...):
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.reqUrl = "https://api.pexels.com/v1/search"
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        window_pane.set_position(300)
        self.reqUrl = "https://api.pexels.com/v1/curated"
        self.query = ""
        self.window.show_options_window(self.options_window.window)
        self.window.show_spinner()
        self.get_page(0)

    def on_change(self, options):
        self.options = options
        if self.query != options["query"]:
            self.query = options["query"]
            self.search(self.query)
