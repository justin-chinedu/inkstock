from sources.remote import RemoteFile, RemotePage, RemoteSource, sanitize_query, SourceType
from sources.svg_source import SvgSource
from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from windows.basic_window import BasicWindow


class FAWindow(BasicWindow):
    name = "fa_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, scale=1,
                            grid_item_height=200,
                            grid_item_width=200,
                            padding=350)

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
        pix.single_preview_scale = 0.3
        pix.preview_scaling = 0.3
        self.source.pix_manager = pix
        return pix


class FAIcon(RemoteFile):
    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name']}-fontawesome"
        self.file_name = self.name + ".svg"
        self.show_name = True


class FAPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source
        self.default_color_task = None

    def get_page_content(self):
        for key, value in self.results:
            name = "-".join(key.split("-")[:-1])
            category = key.split("-")[-1]
            url = f"https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/{category}/{name}.svg"
            info = {
                "id": name,
                "name": name,
                "author": url.split('/')[3],
                "thumbnail": url,
                "license": """The Font Awesome Free download is licensed under a Creative Commons
                    Attribution 4.0 International License and applies to all icons packaged
                    as SVG and JS file types.
                    """,
                "summary": "",
                "file": url,
            }
            if url:
                fa_icon = FAIcon(self.remote_source, info)
                if self.default_color_task:
                    fa_icon.tasks.append(self.default_color_task)
                yield fa_icon


class FASource(SvgSource):
    name = 'Font Awesome Icons'
    desc = "Font Awesome is the Internet's icon library and toolkit, used by millions of designers, developers, " \
           "and content creators. "
    icon = "icons/font-awesome.png"
    source_type = SourceType.ICON
    file_cls = FAIcon
    page_cls = FAPage
    is_default = False
    is_enabled = True
    is_optimized = False
    options_window_width = 350
    items_per_page = 16
    window_cls = FAWindow

    json_path = 'json/font-awesome.json'

    def get_page(self, page_no: int):
        results = self.results[page_no *
                               self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            self.current_page = page_no
            page = FAPage(self, page_no, results)
            page.default_color_task = self.default_color_task
            self.window.add_page(page)

    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.window.show_spinner()
        self.results = [(key, value) for key, value in self.icon_map.items()
                        if key.startswith(query)]
        self.get_page(0)
