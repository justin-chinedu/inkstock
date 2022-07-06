import json

from remote import RemoteFile, RemotePage, RemoteSource, sanitize_query, SourceType
from sources.svg_source import SvgSource
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW
from windows.basic_window import BasicWindow
from windows.options_window import ChangeReceiver


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
        self.file_name = self.name + ".svg"

    def get_thumbnail(self):
        return self.remote.to_local_file(self.info["thumbnail"], self.file_name)

    def get_file(self):
        return self.info["file"]


class UndrawPage(RemotePage, ChangeReceiver):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source
        self.default_color_task = None

    def get_page_content(self):
        for result in self.results:
            illustration = UndrawIllustration(self.remote_source, result)
            if self.default_color_task:
                illustration.tasks.append(self.default_color_task)
            yield illustration


def setup_pixmanager():
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


class UnDraw(SvgSource):
    name = "UnDraw"
    desc = "Open-source illustrations for any idea you can imagine and create."
    icon = "icons/undraw.png"
    source_type = SourceType.ILLUSTRATION
    file_cls = UndrawIllustration
    page_cls = UndrawPage
    is_default = False
    is_enabled = True
    items_per_page = 12
    reqUrl = "https://undraw.co/api/search"
    window_cls = UndrawWindow

    default_svg_color = "#6c63ff"
    default_search_query = "acc"

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)
        self.pix_manager = setup_pixmanager()

    def get_page(self, page_no: int):
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            self.current_page = page_no
            page = UndrawPage(self, page_no, results)
            page.default_color_task = self.default_color_task
            self.window.add_page(page)

    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.window.show_spinner()
        headers_list = {
            "Accept": "*/*",
            "User-Agent": "Inkscape",
            "Content-Type": "application/json"
        }

        payload = json.dumps({"query": query})
        try:
            response = self.session.request("POST", self.reqUrl, data=payload, headers=headers_list)
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
