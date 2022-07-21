import bs4

from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager
from core.utils import asyncme
from sources.source import RemoteSource, SourceType, sanitize_query
from sources.source_file import RemoteFile
from sources.source_page import RemotePage
from windows.basic_window import BasicWindow
from windows.options_window import OptionsChangeListener, OptionsWindow, OptionType

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class BurstWindow(BasicWindow):
    name = "burst_window"

    def __init__(self, gapp):
        # name of the widget file and id
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1)
        self.source.pix_manager = pix
        return pix


class BurstFile(RemoteFile):

    def __init__(self, source, info):
        super().__init__(source, info)
        self.name = f"{self.info['name'][:7]}{self.info['id']}-burst".replace("/", "_")
        self.file_name = self.name + ".jpg"


class BurstPage(RemotePage):
    def __init__(self, remote_source, page_no: int, results):
        super().__init__(remote_source, page_no)
        self.results = results

    def get_page_content(self):
        for result in self.results:
            info = {
                "id": result["id"],
                "thumbnail": result["img_link"],
                "file": result["download_link"],
                "name": result["title"],
                "license": "https://burst.shopify.com/legal/terms"
            }
            yield BurstFile(self.remote_source, info)


class Burst(RemoteSource, OptionsChangeListener):
    name = "Burst"
    desc = "Burst is a free stock photo platform that is powered by Shopify. " \
           "Our image library includes thousands of high-resolution, royalty-free " \
           "images that were shot by our global community of photographers."
    icon = "icons/burst.png"
    file_cls = BurstFile
    page_cls = BurstPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    options_window_width = 300
    window_cls = BurstWindow
    source_type = SourceType.PHOTO

    def __init__(self, cache_dir, import_manager) -> None:
        super().__init__(cache_dir, import_manager)
        self.req_url = "https://burst.shopify.com/photos"
        self.results = []
        self.query = ""
        self.filter = {}
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Burst")
        self.options_window.set_option(
            "filter", ["default", "latest", "downloads"], OptionType.DROPDOWN, "Sort By")

    def get_page(self, page_no: int):
        self.current_page = page_no
        displayed_results = self.items_per_page * (self.current_page + 1)
        if len(self.results) > displayed_results:
            page_results = self.results[
                           page_no * self.items_per_page:(page_no * self.items_per_page) + self.items_per_page]
            page = BurstPage(self, self.current_page, page_results)
        else:
            results = self.extract_results(self.req_url, {"page": self.current_page + 1})
            self.results.extend(results)
            page_results = self.results[
                           page_no * self.items_per_page:(page_no * self.items_per_page) + self.items_per_page]
            page = BurstPage(self, self.current_page, page_results)
        self.window.add_page(page)

    def extract_results(self, url, params=None):
        if params is None:
            params = {}
        params.update(self.filter)
        results = []
        resp = self.session.get(url, params=params)
        print(resp.url)
        soup = BeautifulSoup(resp.content, "html.parser")
        elements = soup.find_all("div", {"class": "photo-card"})
        for elem in elements:
            img = elem.find("img")
            btn = elem.find("button", {"class": "js-download-premium"})
            if btn and img:
                try:
                    img_link = img.get("data-srcset").split(",")[1].strip().split(";")[0].split(" ")[0]
                except AttributeError:
                    img_link = img.get("src")
                info = {
                    "id": img.get("data-photo-id"),
                    "title": img.get("data-photo-title"),
                    "img_link": img_link,
                    "download_link": "https://burst.shopify.com" + btn.get("data-download-url")
                }
                results.append(info)
        return results

    @asyncme.run_or_none
    def get_home(self):
        self.window.clear_pages()
        self.window.show_spinner()
        self.req_url = "https://burst.shopify.com/photos"
        if self.current_page > 0:
            params = {
                "page": self.current_page + 1
            }
            results = self.extract_results(self.req_url, params)
            self.results.extend(results)
        else:
            self.results = []
            results = self.extract_results(self.req_url)
            self.results.extend(results)
        self.get_page(0)

    @asyncme.run_or_none
    def search(self, query):
        self.req_url = "https://burst.shopify.com/photos/search"
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.results = []
        params = {
            "q": self.query.replace("%20", "+")
        }
        results = self.extract_results(self.req_url, params)
        self.results.extend(results)
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.query = ""
        self.get_home()

    def on_change(self, options):
        if not self.window:
            return

        if "filter" in options:
            if options["filter"] == "default":
                self.filter = {}
            else:
                self.filter = {"sort": options["filter"]}
            if not options["query"]:
                self.get_home()
                return

        self.query = sanitize_query(options["query"])
        self.options = options
        if self.window and self.query:
            self.search(self.query)
            return
