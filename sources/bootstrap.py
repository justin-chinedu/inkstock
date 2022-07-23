import os

from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from core.utils import asyncme
from sources.source import RemoteSource, sanitize_query, SourceType
from sources.source_file import RemoteFile
from sources.source_page import RemotePage, NoResultsPage
from sources.svg_source import SvgSource
from windows.basic_window import BasicWindow


class BootstrapWindow(BasicWindow):
    name = "bootstrap_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, scale=8,
                            grid_item_height=200,
                            grid_item_width=200,
                            padding=120)

        pix.enable_aspect = False
        pix.preview_scaling = 7
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


class BootstrapIcon(RemoteFile):
    def __init__(self, source, info):
        super().__init__(source, info)
        self.name = f"{self.info['name']}-bootstrap-icon"
        self.file_name = self.name + ".svg"
        self.show_name = True

    def get_thumbnail(self):
        svg = self.info["thumbnail"]
        with open(os.path.join(CACHE_DIR, self.file_name), mode="w+") as f:
            f.write(svg)
            f.flush()
        return os.path.join(CACHE_DIR, self.file_name)


class BootstrapIconsPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source
        self.default_color_task = None

    def get_page_content(self):
        for name, svg in self.results:

            info = {
                "id": name,
                "name": name,
                "thumbnail": svg,
                "license": "",
                "file": svg,
            }

            icon = BootstrapIcon(self.remote_source, info)
            if self.default_color_task:
                icon.tasks.append(self.default_color_task)
            yield icon


class BootstrapIconsSource(SvgSource):
    name = 'Bootstrap Icons'
    desc = "Free, high quality, open source icon library with over 1,600 icons. " \
           "Include them anyway you like?SVGs, SVG sprite, or web fonts"
    icon = "icons/bootstrap.png"
    source_type = SourceType.ICON
    file_cls = BootstrapIcon
    page_cls = BootstrapIconsPage
    is_default = True
    is_enabled = True
    is_optimized = False
    options_window_width = 300
    items_per_page = 16
    window_cls = BootstrapWindow

    json_path = 'json/bootstrap.json'

    def get_page(self, page_no: int):
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            self.current_page = page_no
            page = BootstrapIconsPage(self, page_no, results)
            page.default_color_task = self.default_color_task
            self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.window.show_spinner()
        self.results = [(key.split(".")[0], value) for key, value in self.icon_map.items()
                        if key.startswith(query)]
        if not self.results:
            self.window.add_page(NoResultsPage(query))
        else:
            self.get_page(0)
