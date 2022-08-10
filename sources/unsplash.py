from core.utils import asyncme
from keys import KEYS
from sources.source import RemoteSource, SourceType, sanitize_query
from sources.source_page import RemotePage, NoResultsPage
from sources.source_file import RemoteFile, NoMoreResultsFile
from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager

from windows.basic_window import BasicWindow
from windows.options_window import OptionsChangeListener, OptionType, OptionsWindow


class UnsplashWindow(BasicWindow):
    name = "unsplash_window"

    def __init__(self, gapp):
        # name of the widget file and id 
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmap_manager(self):
        pix = PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1)
        self.source.pix_manager = pix
        return pix


class UnsplashFile(RemoteFile):

    def __init__(self, source, info, headers):
        super().__init__(source, info)
        self.headers = headers
        self.name = f"{self.info['name'][:7]}{self.info['id']}-unsplash".replace("/", "_")
        self.file_name = self.name + ".jpg"

    def get_thumbnail(self):
        view_trigger = self.info["view_link"]
        self.source.session.head(view_trigger, headers=self.headers)
        return self.source.to_local_file(self.info["thumbnail"], self.file_name, self.headers)

    def get_file(self):
        download_trigger = self.info["download_link"]
        self.source.session.head(download_trigger, headers=self.headers)
        return super().get_file()
        # return self.remote.to_local_file(self.info["file"], self.file_name, self.headers)


class UnsplashPage(RemotePage):
    def __init__(self, remote_source, page_no: int, query):
        super().__init__(remote_source, page_no)
        self.query = query

    def get_page_content(self):
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "InkStock",
            "Content-Type": "application/json",
            "Accept-Version": "v1",
            "Authorization": KEYS["unsplash"]
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

            if len(json_response) == 0:
                yield NoMoreResultsFile(query=self.query)

            for photo in json_response:
                info = {
                    "id": photo["id"],
                    "width": photo["width"],
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
                    "license": "https://unsplash.com/license"
                }

                file = UnsplashFile(self.remote_source, info, headers_list)
                yield file
                # photos.append(file)
            # return photos
        except Exception as err:
            print("Error trying to establish connection")


class Unsplash(RemoteSource, OptionsChangeListener):
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
    options_window_width = 350
    reqUrl = "https://api.unsplash.com/search/photos"
    window_cls = UnsplashWindow
    source_type = SourceType.PHOTO

    def __init__(self, cache_dir, import_manager) -> None:
        super().__init__(cache_dir, import_manager)
        self.query = ""
        # setting defaults
        self.options = {
            "order_by": "relevant",
            "orientation": "all",
            "content_filter": "low",
            "color": "all"
        }
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
        self.options_window.set_option("info", "", OptionType.TEXTVIEW, show_separator=False)
        self.options_window.set_option("profile_link", "", OptionType.LINK, label="View Profile", attach=False)

    def get_page(self, page_no: int):
        self.current_page = page_no
        page = UnsplashPage(self, self.current_page, self.query)
        self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query):
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.reqUrl = "https://api.unsplash.com/search/photos"
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.reqUrl = "https://api.unsplash.com/photos"
        self.query = ""
        asyncme.run_or_none(self.get_page)(0)

    def on_change(self, options):
        self.query = sanitize_query(options["query"])
        self.options = options
        if self.window and self.query:
            self.search(self.query)
            return

    def file_selected(self, file: RemoteFile):
        info = file.info
        text = f'<span  size="large" weight="normal" >Photo by</span>\n\n' + \
               f'<span  size="large" weight="bold" >{info["photographer"]}</span>\n\n' + \
               (f'<span  size="medium" weight="normal" >{info["name"]}</span>\n\n' if info["name"] else '') + \
               f'<span  size="medium" weight="normal" >Available under the UnSplash License, <a href="{info["license"]}">More Info</a></span>'
        text.replace("&", "&amp;")
        self.options_window.options["info"].view.set_markup(text)
        if info["photographer_url"]:
            self.options_window.attach_option("profile_link")
            self.options_window.options["profile_link"].view.set_uri(info["photographer_url"])
