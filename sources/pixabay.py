from inkex.gui import asyncme
from remote import RemoteFile, RemotePage, RemoteSource
import json
import sys
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager

from windows.basic_window import BasicWindow
from windows.options_window import ChangeReciever, OptionType, OptionsWindow
from windows.results_window import ResultsWindow
from gi.repository import Gtk


class PixabayWindow(BasicWindow):
    name = "pixabay_window"

    def __init__(self, gapp):
        # name of the widget file and id 
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        return PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1)

    def on_results_created(self, results: ResultsWindow):
        results_flow: Gtk.FlowBox = results.results.widget
        result_item = results.results.builder.get_object("result_item")
        # result_item.set_hexpand(False)


class PixabayFile(RemoteFile):

    def __init__(self, remote, info, headers):
        super().__init__(remote, info)
        self.headers = headers
        self.name = f"{self.id}-{self.info['id']}-pixabay"

    @property
    def thumbnail(self):
        view_trigger = self.info["view_link"]
        # self.remote.session.get(view_trigger, headers=self.headers)
        name = self.name + ".jpg"
        return self.remote.to_local_file(self.info["thumbnail"], name, self.headers)

    def get_file(self):
        download_trigger = self.info["download_link"]
        self.remote.session.get(download_trigger, headers=self.headers)
        name = self.name + "file.jpg"
        return self.remote.to_local_file(self.info["file"], name, self.headers)


class PixabayPage(RemotePage):
    def __init__(self, remote_source, page_no: int, query):
        super().__init__(remote_source, page_no)
        self.query = query

    def get_page_content(self):
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "Inkscape",
            "Content-Type": "application/json",
        }

        params = {"order": self.remote_source.options["order"],
                  "orientation": self.remote_source.options["orientation"],
                  "image_type": self.remote_source.options["image_type"]}

        if self.query:
            params["q"] = self.query

        color = self.remote_source.options.get("colors", None)
        if color and color != "all":
            params["colors"] = self.remote_source.options["colors"]
        category = self.remote_source.options.get("category", None)
        if category and category != "all":
            params["category"] = self.remote_source.options["category"]

        params["per_page"] = self.remote_source.items_per_page
        params["page"] = self.page_no + 1
        params["key"] = "10377294-d1bbb9384e56deb909bb35d1f"

        try:
            response = self.remote_source.session.request(
                "GET", self.remote_source.reqUrl, params=params, headers=headers_list)
            photos = []
            json_response = response.json()

            for photo in json_response["hits"]:
                info = {
                    "id": photo["id"],
                    "url": photo["largeImageURL"],
                    "user": photo["user"],
                    "user_url": "https://pixabay.com/users/" + photo["user"] + "-" + str(photo["user_id"]),
                    "user_id": photo["user_id"],
                    "thumbnail": photo["webformatURL"],
                    "file": photo["largeImageURL"],
                    "name": "",
                    "view_link": photo["pageURL"],
                    "license": "Pixabay Licence"
                }

                photos.append(PixabayFile(self.remote_source, info, headers_list))
            return photos
        except Exception as err:
            print("Error trying to establish connection")


class Pixabay(RemoteSource, ChangeReciever):
    name = "Pixabay"
    desc = "Over 2.6 million+ high quality stock images, videos and music shared by our talented community."
    icon = "icons/pixabay.png"
    file_cls = PixabayFile
    page_cls = PixabayPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    reqUrl = "https://pixabay.com/api/"
    window_cls = PixabayWindow

    def __init__(self, cache_dir) -> None:
        super().__init__(cache_dir)
        self.query = ""
        # setting defaults
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("q", None, OptionType.SEARCH, "Search Pixabay")
        self.options_window.set_option(
            "order", ["popular", "latest"], OptionType.DROPDOWN, "Order by")
        self.options_window.set_option(
            "orientation", ["all", "horizontal", "vertical"], OptionType.DROPDOWN, "Choose orientation")
        self.options_window.set_option(
            "image_type", ["all", "photo", "illustration", "vector"], OptionType.DROPDOWN, "Image type")
        self.options_window.set_option(
            "category", ["all", "backgrounds", "fashion", "nature", "science", "education", "feelings", "health",
                         "people", "religion", "places", "animals", "industry", "computer", "food", "sports",
                         "transportation", "travel", "buildings", "business", "music"], OptionType.DROPDOWN, "Category")
        self.options_window.set_option(
            "colors",
            ["all", "grayscale", "transparent", "red", "orange", "yellow", "green", "turquoise", "blue", "lilac",
             "pink", "white", "gray", "black", "brown"], OptionType.DROPDOWN, "Preferred color")

    @asyncme.run_or_none
    def get_page(self, page_no: int):
        self.current_page = page_no
        page = PixabayPage(self, self.current_page, self.query)
        self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query, tags=...):
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        window_pane.set_position(350)
        self.query = ""
        self.window.show_options_window(self.options_window.window)
        self.window.show_spinner()
        self.get_page(0)

    def on_change(self, options):
        self.options = options
        if self.query != options["q"]:
            self.query = options["q"]
            self.search(self.query)
