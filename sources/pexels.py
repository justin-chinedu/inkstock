from core.utils import asyncme
from keys import KEYS
from sources.source import RemoteFile, RemotePage, RemoteSource, sanitize_query, SourceType
from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager

from windows.basic_window import BasicWindow
from windows.options_window import OptionsChangeListener, OptionType, OptionsWindow


class PexelsWindow(BasicWindow, OptionsChangeListener):
    name = "pexels_window"

    def __init__(self, gapp):
        # name of the widget file and id 
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1)
        self.source.pix_manager = pix
        return pix


class PexelsFile(RemoteFile):
    def __init__(self, source, info, headers):
        super().__init__(source, info)
        self.headers = headers
        self.name = f"{self.info['name'][:7]}{self.info['id']}-pexels".replace("/", "_")
        self.file_name = self.name + ".png"

    def get_thumbnail(self):
        return self.source.to_local_file(self.info["thumbnail"], self.file_name, self.headers)


class PexelsPage(RemotePage):
    def __init__(self, remote_source, page_no: int, query):
        super().__init__(remote_source, page_no)
        self.query = query

    def get_page_content(self):
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "InkStock",
            "Content-Type": "application/json",
            "Authorization": KEYS["pexels"]
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
                    "license": "https://www.pexels.com/license/"
                }

                file = PexelsFile(self.remote_source, info, headers_list)
                yield file
                # photos.append(file)
            # return photos
        except Exception as e:
            print(str('Exception: ' + e))
            return []


class Pexels(RemoteSource, OptionsChangeListener):
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
    source_type = SourceType.PHOTO

    def __init__(self, cache_dir, import_manager) -> None:
        super().__init__(cache_dir, import_manager)
        self.query = ""
        # setting defaults
        self.options = {
            "orientation": "landscape",
            "size": "large"
        }
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Pexels")
        self.options_window.set_option("orientation", [
            "landscape", "portrait", "square"], OptionType.DROPDOWN, "Choose orientation")
        self.options_window.set_option(
            "size", ["large", "medium", "small"], OptionType.DROPDOWN, "Download size of photo")
        self.options_window.set_option(
            "color", None, OptionType.COLOR, "Choose preferred color")
        self.options_window.set_option("info", "", OptionType.TEXTVIEW, show_separator=False)
        self.options_window.set_option("profile_link", "", OptionType.LINK, label="View Profile", attach=False)

    def get_page(self, page_no: int):
        self.current_page = page_no
        page = PexelsPage(self, self.current_page, self.query)
        self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query):
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.reqUrl = "https://api.pexels.com/v1/search"
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.reqUrl = "https://api.pexels.com/v1/curated"
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
               f'<span  size="large" weight="bold" >{info["photographer"]}</span>\n\n' + \
               (f'<span  size="medium" weight="normal" >{info["name"]}</span>\n\n' if info["name"] else '') + \
               f'<span  size="medium" weight="normal" >Available under the Pexels License, <a href="{info["license"]}">More Info</a></span>'
        text.replace("&", "&amp;")
        self.options_window.options["info"].view.set_markup(text)
        if info["photographer_url"]:
            self.options_window.attach_option("profile_link")
            self.options_window.options["profile_link"].view.set_uri(info["photographer_url"])
