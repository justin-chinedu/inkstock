import re
import uuid
from urllib.parse import urljoin

from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from core.utils import asyncme
from sources.source import RemoteSource, SourceType, sanitize_query
from sources.source_file import RemoteFile
from sources.source_page import RemotePage, NoResultsPage
from windows.basic_window import BasicWindow
from windows.options_window import OptionsChangeListener, OptionsWindow, OptionType

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


class OpenClipArtWindow(BasicWindow):
    name = "open_clip_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmap_manager(self):
        pix = PixmapManager(CACHE_DIR, scale=0.5,
                            grid_item_height=200,
                            grid_item_width=200,
                            padding=120)

        pix.enable_aspect = False
        pix.preview_scaling = 0.3
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


class OpenClipArtSvg(RemoteFile):
    def __init__(self, source, info):
        super().__init__(source, info)
        self.name = f"{self.info['name']}-open-clip"
        self.file_name = self.name + ".svg"
        self.show_name = False
        self.id = uuid.uuid4()


class OpenClipArtPage(RemotePage):
    def __init__(self, remote_source, page_no: int, results):
        super().__init__(remote_source, page_no)
        self.results = results

    def get_page_content(self):
        for result in self.results:
            info = {
                "thumbnail": result["img_link"],
                "file": result["download_link"],
                "name": result["title"],
                "license": "cc-0"
            }
            yield OpenClipArtSvg(self.remote_source, info)


class OpenClipArt(RemoteSource, OptionsChangeListener):
    name = "Open Clipart"
    desc = "Founded in 2004, Open Clipart is an online media collection" \
           " of more than 160 000 vectorial graphics, entirely in the public domain."
    icon = "icons/openclipart.png"
    file_cls = OpenClipArtSvg
    page_cls = OpenClipArtPage
    is_default = False
    is_enabled = True if BeautifulSoup else False
    items_per_page = 12
    options_window_width = 300
    window_cls = OpenClipArtWindow
    source_type = SourceType.ILLUSTRATION

    def __init__(self, cache_dir, import_manager) -> None:
        super().__init__(cache_dir, import_manager)
        self.page_offset = 0
        self.options = {}
        self.results = []
        self.query = ""
        self.req_url = "https://openclipart.org/search/"
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, f"Search {self.name}")

    def get_page(self, page_no: int):
        displayed_results = self.items_per_page * (self.current_page + 1)
        page_results = []
        while len(self.results) < displayed_results:
            param = {"p": self.current_page + 1 + self.page_offset} if self.query == "" \
                else {"p": self.current_page + 1 + self.page_offset, "query": self.query}
            results = self.extract_results(self.req_url, param)
            self.results.extend(results)
            if not results:
                break
        else:
            self.current_page = page_no
            page_results = self.results[
                           self.current_page * self.items_per_page:
                           (self.current_page * self.items_per_page) + self.items_per_page
                           ]
        if page_results:
            page = OpenClipArtPage(self, self.current_page, page_results)
            self.window.add_page(page)
        elif page_no == 0 and self.query:
            self.window.add_page(NoResultsPage(self.query.replace("%20", "+")))

    @asyncme.run_or_none
    def get_home(self):
        self.query = ""
        self.search(self.query)

    @asyncme.run_or_none
    def search(self, query):
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.results = []
        self.current_page = 0
        self.get_page(0)

    def extract_results(self, url, params=None):
        if params is None:
            params = {}
        results = []
        max_tries = 2
        # open clip art weirdly returns empty pages so...
        for i in range(max_tries):
            resp = self.session.get(url, params=params)
            soup = BeautifulSoup(resp.content, "html.parser")
            divs = soup.find_all("div", {"class": "artwork"})
            for div in divs:

                if div.a and div.a.img:
                    img = div.a.img
                    link = urljoin(self.req_url, div.a.get("href"))
                    p = re.compile("detail/(\\d+)/")
                    svg_id = p.findall(link)[0]
                    img_link = f"https://openclipart.org/image/800px/{svg_id}"
                    d_link = f"https://openclipart.org/download/{svg_id}"

                    info = {
                        "title": img.get("alt") if "alt" in img else svg_id,
                        "img_link": img_link,
                        "download_link": d_link
                    }
                    results.append(info)
            if results:
                break
            else:
                self.page_offset += 1
                params["p"] = self.current_page + 1 + self.page_offset
        return results

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.query = ""
        self.get_home()

    def on_change(self, options):
        if not self.window:
            return

        query = sanitize_query(options["query"])

        if query and self.query != query:  # if search query changed
            self.query = query
            self.options = options
            self.search(self.query)
            return
