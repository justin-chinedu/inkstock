import sys

from core.utils import asyncme
from sources.svg_source import SvgSource
from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW

from windows.basic_window import BasicWindow
from windows.options_window import OptionType

sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from sources.source import RemoteFile, RemotePage, RemoteSource, sanitize_query, SourceType


class JoeschmoeWindow(BasicWindow):
    name = "joescchmoe_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, pref_width=600,
                            pref_height=600, scale=4,
                            grid_item_height=400,
                            grid_item_width=400,
                            padding=20,
                            aspect_ratio=SIZE_ASPECT_GROW)
        pix.style = """.{id}{{
            background-color: white;
            background-size: contain;
            background-repeat: no-repeat;
            background-origin: content-box;
            background-image: url("{url}");
            }}
            
            window flowbox > flowboxchild *{{
            border-radius: 5%;
            }}
        """
        self.source.pix_manager = pix
        return pix


class JoeschmoeIllustration(RemoteFile):

    def __init__(self, source, info):
        super().__init__(source, info)
        self.name = f"{self.info['name']}-joeschmoe"
        self.file_name = self.name + ".svg"


class JoeschmoePage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, url):
        super().__init__(remote_source, page_no)
        self.remote_source = remote_source
        self.url = url
        self.default_color_task = None

    def get_page_content(self):
        info = {
            "name": self.remote_source.query,
            "file": self.url,
            "thumbnail": self.url,
            "license": ""
        }
        illustration = JoeschmoeIllustration(self.remote_source, info)
        if self.default_color_task:
            illustration.tasks.append(self.default_color_task)
        yield illustration


class JoeschmoeSource(SvgSource):
    name = "Joeschmoe"
    desc = "Joe Schmoes are colorful characters illustrated by Jon&amp;Jess that can be used as profile picture " \
           "placeholders for live websites or design mock ups. "
    icon = "icons/joeschmoe.png"
    source_type = SourceType.ILLUSTRATION
    file_cls = JoeschmoeIllustration
    page_cls = JoeschmoePage
    is_default = False
    is_enabled = True
    items_per_page = 8
    reqUrl = "https://joeschmoe.io/api/v1{gender}{seed}"
    window_cls = JoeschmoeWindow
    default_svg_color = "#fce7d4"
    default_search_query = "jane"

    def __init__(self, cache_dir, import_manager):
        super().__init__(cache_dir, import_manager)
        self.options_window.set_option(
            "gender", ["all", "female", "male"], OptionType.DROPDOWN, "Choose gender")
        self.options_window.set_option("no_of_avatars", 1, OptionType.TEXTFIELD, "No of avatars")
        self.options_window.set_option("random", self.random_clicked, OptionType.BUTTON, "Generate random avatars")

    def get_page(self, page_no: int, req_url=None):
        if page_no == 0:
            self.current_page = page_no
            page = JoeschmoePage(self, page_no, req_url)
            self.window.add_page(page)

    def random_clicked(self, option):
        req_url = "https://joeschmoe.io/api/v1/random"
        self.window.clear_pages()
        self.window.show_spinner()
        self.get_page(0, req_url)

    @asyncme.run_or_none
    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.clear_color_options()
        self.window.show_spinner()
        gender = self.options["gender"] if "gender" in self.options else "all"
        if gender != "all":
            req_url = self.reqUrl.format(gender=f"/{gender}", seed=f"/{query}")
        else:
            req_url = self.reqUrl.format(gender="", seed=f"/{query}")

        self.get_page(0, req_url)
