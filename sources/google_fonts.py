import io
import json
import os
from os.path import exists

from inkex.gui import asyncme
from remote import RemotePage, RemoteSource, SourceType
from sources.font_file import FontFile
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_CROP
from utils.text_to_png import render_text_to_png
from windows.basic_window import BasicWindow
from windows.options_window import ChangeReceiver, OptionsWindow, OptionType


class GoogleFontsWindow(BasicWindow, ChangeReceiver):
    name = "google_fonts_window"

    def __init__(self, gapp):
        # name of the widget file and id
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, pref_width=600, pref_height=500, scale=1, aspect_ratio=SIZE_ASPECT_CROP,
                            grid_item_height=400, grid_item_width=450)
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


class GoogleFontFile(FontFile):
    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name']}-google-fonts"
        self.file_name = self.name + ".ttf"

    def get_thumbnail(self):
        file_name = self.name + ".png"
        font_data = self.remote.to_local_file(self.info["thumbnail"], file_name, content=True)
        file_path = os.path.join(self.remote.cache_dir, file_name)
        render_text_to_png(font_file=io.BytesIO(font_data), save_path=file_path, text=self.text,
                           spacing=self.line_spacing, font_size=self.font_size, text_color=self.color,
                           bg_color=self.bg_color)
        return file_name


class GoogleFontsPage(RemotePage):
    def get_page_content(self):
        for name, url in self.results:
            info = {
                "name": name,
                "thumbnail": url,
                "file": url,
                "license": "OFL"
            }
            font = GoogleFontFile(self.remote_source, info)
            yield font

    def __init__(self, remote_source, page_no: int, results):
        super().__init__(remote_source, page_no)
        self.results = results


class GoogleFontsSource(RemoteSource, ChangeReceiver):
    name = "Google Fonts"
    desc = "Google Fonts is a computer font and web font service owned by Google. This includes free and open source " \
           "font families, an interactive web directory for browsing the library, and APIs for using the fonts via " \
           "CSS and Android. "
    icon = "icons/google_fonts.jpg"
    source_type = SourceType.FONT
    file_cls = GoogleFontFile
    page_cls = GoogleFontsPage
    is_default = False
    is_enabled = True
    items_per_page = 4
    window_cls = GoogleFontsWindow

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)
        self.results = []
        self.query = ""
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Google Fonts")

        # ------init font file --------#
        if exists("json/google_fonts.json"):
            with open("json/google_fonts.json", mode="r") as f:
                self.fonts = json.load(f)
        else:
            self.is_enabled = False

    def get_page(self, page_no: int):
        self.current_page = page_no
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            page = GoogleFontsPage(self, page_no, results)
            self.window.add_page(page)

    def search(self, query):
        self.results = []
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        self.results = [(key, value) for key, value in self.fonts.items()
                        if query in key.lower()]
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.query = "a"
        asyncme.run_or_none(self.search)("a")

    def on_change(self, options):
        self.options = options
        if self.window and self.query != options["query"] and options["query"]:
            self.query = options["query"]
            self.search(self.query)
            return
