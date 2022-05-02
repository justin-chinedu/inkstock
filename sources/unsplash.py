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


class UnsplashWindow(BasicWindow):
    name = "pexels_window"

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


class UnsplashFile(RemoteFile):

    def __init__(self, remote, info, headers):
        super().__init__(remote, info)
        self.headers = headers
        self.name = f"{self.info['name'][:7]}-{self.info['id']}-unsplash"

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


class UnsplashPage(RemotePage):
    def __init__(self, remote_source, page_no: int, query):
        super().__init__(remote_source, page_no)
        self.query = query

    def get_page_content(self):
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "Inkscape",
            "Content-Type": "application/json",
            "Accept-Version": "v1",
            "Authorization": "Client-ID YsYs_gNo_yWWvaWHttBYA1i6YiDOeFkvioL3oZ0Y6ck"
        }

        params = {}
        if self.query:
            params["query"] = self.query
        params["order_by"] = self.remote_source.options["order_by"]

        searching = self.remote_source.reqUrl == "https://api.unsplash.com/search/photos"
        if searching:
            if self.remote_source.options["orientation"] != "all":
                params["orientation"] = self.remote_source.options["orientation"]
            params["content_filter"] = self.remote_source.options["content_filter"]

            color = self.remote_source.options.get("color", None)
            if color and color != "all":
                if color == "B & W":
                    color = "black_and_white"
                color = color.replace(" ", "_")
                params["color"] = color

        params["per_page"] = self.remote_source.items_per_page
        params["page"] = self.page_no + 1

        try:
            response = self.remote_source.session.request(
                "GET", self.remote_source.reqUrl, params=params, headers=headers_list)
            photos = []
            if searching:
                json_response = response.json()["results"]
            else:
                json_response = response.json()

            for photo in json_response:
                info = {
                    "id": photo["id"], "width": photo["width"],
                    "height": photo["height"],
                    "url": photo["urls"]["full"],
                    "photographer": photo["user"]["name"],
                    "photographer_url": photo["user"]["portfolio_url"],
                    "photographer_id": photo["user"]["id"],
                    "color": photo["color"],
                    "thumbnail": photo["urls"]["small"],
                    "file": photo["urls"]["full"],
                    "name": "" if not photo["description"] else photo["description"],
                    "view_link": photo["links"]["self"],
                    "download_link": photo["links"]["download"],
                    "license": "Unsplash Licence"
                }

                photos.append(UnsplashFile(self.remote_source, info, headers_list))
            return photos
        except Exception as err:
            print("Error trying to establish connection")


class Unsplash(RemoteSource, ChangeReciever):
    name = "Unsplash"
    desc = "Unsplash is a website dedicated to sharing stock photography under the Unsplash license." \
           "Unsplash has over 265,000 contributing photographers and generates more than " \
           "16 billion photo impressions per month "
    icon = "icons/unsplash.svg"
    file_cls = UnsplashFile
    page_cls = UnsplashPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    reqUrl = "https://api.unsplash.com/search/photos"
    window_cls = UnsplashWindow

    def __init__(self, cache_dir) -> None:
        super().__init__(cache_dir)
        self.query = ""
        # setting defaults
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Unsplash")
        self.options_window.set_option(
            "order_by", ["relevant", "latest"], OptionType.DROPDOWN, "Order By")
        self.options_window.set_option(
            "orientation", ["all", "landscape", "portrait", "squarish"], OptionType.DROPDOWN, "Choose orientation")
        self.options_window.set_option(
            "content_filter", ["low", "high"], OptionType.DROPDOWN, "Content Filter")
        self.options_window.set_option("color", [
            "all", "B & W", "black", "white", "orange", "yellow", "red",
            "purple", "magenta", "green", "teal", "blue"],
                                       OptionType.DROPDOWN, "Choose preferred color")

    @asyncme.run_or_none
    def get_page(self, page_no: int):
        self.current_page = page_no
        page = UnsplashPage(self, self.current_page, self.query)
        self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query, tags=...):
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.reqUrl = "https://api.unsplash.com/search/photos"
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        window_pane.set_position(350)
        self.reqUrl = "https://api.unsplash.com/photos"
        self.query = ""
        self.window.show_options_window(self.options_window.window)
        self.window.show_spinner()
        self.get_page(0)

    def on_change(self, options):
        self.options = options
        if self.query != options["query"]:
            self.query = options["query"]
            self.search(self.query)