from core.utils import asyncme
from keys import KEYS
from sources.source import RemoteFile, RemotePage, RemoteSource, SourceType, sanitize_query
from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager

from windows.basic_window import BasicWindow
from windows.options_window import OptionsChangeListener, OptionType, OptionsWindow


class PixabayWindow(BasicWindow):
    name = "pixabay_window"

    def __init__(self, gapp):
        # name of the widget file and id 
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1)
        self.source.pix_manager = pix
        return pix


class PixabayFile(RemoteFile):

    def __init__(self, source, info, headers):
        super().__init__(source, info)
        self.headers = headers
        self.name = f"{self.info['id']}-pixabay"
        self.file_name = self.name + ".jpg"

    def get_thumbnail(self):
        view_trigger = self.info["view_link"]
        self.source.session.head(view_trigger, headers=self.headers)
        return self.source.to_local_file(self.info["thumbnail"], self.file_name, self.headers)


class PixabayPage(RemotePage):
    def __init__(self, remote_source, page_no: int, query):
        super().__init__(remote_source, page_no)
        self.query = query

    def get_page_content(self):
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "InkStock",
            "Content-Type": "application/json",
        }

        params = {"order": self.remote_source.options["order"],
                  "orientation": self.remote_source.options["orientation"],
                  "image_type": self.remote_source.options["image_type"]}

        if self.query:
            params["query"] = self.query

        color = self.remote_source.options.get("colors", None)
        if color and color != "all":
            params["colors"] = self.remote_source.options["colors"]
        category = self.remote_source.options.get("category", None)
        if category and category != "all":
            params["category"] = self.remote_source.options["category"]

        params["per_page"] = self.remote_source.items_per_page
        params["page"] = self.page_no + 1
        params["key"] = KEYS["pixabay"]

        try:
            response = self.remote_source.session.request(
                "GET", self.remote_source.reqUrl, params=params, headers=headers_list)

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
                    "license": "https://pixabay.com/service/license/"
                }

                file = PixabayFile(self.remote_source, info, headers_list)
                yield file

        except Exception as err:
            print(f"Error(Pixabay) couldn't fetch images {err}")
            return []


class Pixabay(RemoteSource, OptionsChangeListener):
    name = "Pixabay"
    desc = "Over 2.6 million+ high quality stock images, videos and music shared by our talented community."
    icon = "icons/pixabay.png"
    file_cls = PixabayFile
    page_cls = PixabayPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    options_window_width = 350
    reqUrl = "https://pixabay.com/api/"
    window_cls = PixabayWindow
    source_type = SourceType.PHOTO

    def __init__(self, cache_dir, import_manager) -> None:
        super().__init__(cache_dir, import_manager)
        self.query = ""
        # setting defaults
        self.options = {
            "order": "popular",
            "orientation": "all",
            "image_type": "all",
            "category": "all",
            "colors": "all"
        }
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Pixabay")
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
        self.options_window.set_option("info", "", OptionType.TEXTVIEW, show_separator=False)
        self.options_window.set_option("profile_link", "", OptionType.LINK, label="View Profile", attach=False)

    def get_page(self, page_no: int):
        self.current_page = page_no
        page = PixabayPage(self, self.current_page, self.query)
        self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query):
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.query = ""
        asyncme.run_or_none(self.get_page)(0)

    def on_change(self, options):
        if not self.window:
            return

        query = sanitize_query(options["query"])
        # if search query changed
        if query and self.query != query:
            self.query = query
            self.options = options
            self.search(self.query)
            return

    def file_selected(self, file: RemoteFile):
        info = file.info
        text = f'<span  size="large" weight="normal" >Photo by</span>\n\n' + \
               f'<span  size="large" weight="bold" >{info["user"]}</span>\n\n' + \
               (f'<span  size="medium" weight="normal" >{info["name"]}</span>\n\n' if info["name"] else '') + \
               f'<span  size="medium" weight="normal" >Available under the Pixabay License, <a href="{info["license"]}">More Info</a></span>'
        text.replace("&", "&amp;")
        self.options_window.options["info"].view.set_markup(text)
        if info["user_url"]:
            self.options_window.attach_option("profile_link")
            self.options_window.options["profile_link"].view.set_uri(info["user_url"])
