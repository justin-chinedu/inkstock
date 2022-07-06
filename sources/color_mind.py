import os

from inkex.gui import asyncme
from remote import RemoteFile, RemotePage, RemoteSource, sanitize_query, SourceType
from sources.svg_source import SvgSource
from tasks.svg_color_replace import SvgColorReplace
from utils.color_palette import gen_random_svg_palettes
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW, SIZE_ASPECT_CROP
from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType, ColorOption
from windows.view_change_listener import ViewChangeListener


class ColorMindWindow(BasicWindow):
    name = "color_mind_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, scale=8,
                            grid_item_height=200,
                            grid_item_width=300,
                            padding=20)

        pix.enable_aspect = False
        pix.preview_scaling = 1
        pix.preview_padding = 30
        pix.preview_aspect_ratio = SIZE_ASPECT_CROP
        pix.preview_item_height = 200
        pix.preview_item_width = 300
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


class ColorMindPalette(RemoteFile):
    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name']}-color-mind"
        self.file_name = self.name + ".svg"

    def get_thumbnail(self):
        thumbnail = self.info["thumbnail"]
        file_path = os.path.join(self.remote.cache_dir, self.file_name)
        with open(file_path, mode="w+") as f:
            f.writelines(thumbnail)
        return self.file_name

    def get_file(self):
        file = self.info["file"]
        file_path = os.path.join(self.remote.cache_dir, self.file_name)
        with open(file_path, mode="w+") as f:
            f.writelines(file)
        return self.file_name


class ColorMindPalettesPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source
        self.default_color_task = None

    def get_page_content(self):
        for palette in self.results:
            ID = str(id(palette))
            info = {
                "id": ID,
                "name": "swatch" + ID,
                "author": "Color mind",
                "thumbnail": palette,
                "license": "",
                "summary": "",
                "file": palette,
            }
            palette = ColorMindPalette(self.remote_source, info)
            if self.default_color_task:
                palette.tasks.append(self.default_color_task)
            yield palette


class ColorMindPalettesSource(RemoteSource, ViewChangeListener):
    name = 'ColorMind'
    desc = "ColorMind is a color scheme generator that uses deep learning." \
           " It can learn color styles from photographs, movies, and popular art."
    icon = "icons/color_mind.svg"
    source_type = SourceType.SWATCH
    file_cls = ColorMindPalette
    page_cls = ColorMindPalettesPage
    is_default = True
    is_enabled = True
    is_optimized = False
    options_window_width = 350
    items_per_page = 16
    window_cls = ColorMindWindow

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)
        self.last_selected_file = None
        self.color_ext = SvgColorReplace()
        self.default_color_task = None
        self.results = []
        self.options = {}
        self.search_color = None
        self.options_window = OptionsWindow(self)
        self.search_color_option: ColorOption = self.options_window.set_option(
            "search_color", None, OptionType.COLOR, "Swatch from color")
        self.options_window.set_option("random", self.gen_random_palettes, OptionType.BUTTON,
                                       "Random", show_separator=False)

    def get_page(self, page_no: int):
        results = gen_random_svg_palettes(self.items_per_page)
        if results:
            self.current_page = page_no
            page = ColorMindPalettesPage(remote_source=self, page_no=page_no, results=results)
            page.default_color_task = self.default_color_task
            self.window.add_page(page)

    @asyncme.run_or_none
    def gen_random_palettes(self, name: str):
        self.window.clear_pages()
        self.get_page(0)

    @asyncme.run_or_none
    def gen_swatch_palettes(self, name: str):
        self.window.clear_pages()
        self.get_page(0)

    @asyncme.run_or_none
    def search(self, query):
        self.get_page(0)

    @asyncme.mainloop_only
    def file_selected(self, file: RemoteFile):
        if file != self.last_selected_file:
            self.last_selected_file = file

    def files_selection_changed(self, files: list[RemoteFile]):
        super().files_selection_changed(files)
        # multiple file selection could occur without triggering
        # a single selection

        if files and self.window.results.is_multi_view():  # List would be cleared on search, so we avoid index error
            first_item = files[0]
            self.file_selected(first_item)
            if "similar_swatch" in self.options_window.options.keys():
                self.options_window.remove_option("similar_swatch")
                self.options_window.set_option("similar_swatch", self.gen_random_palettes, OptionType.BUTTON,
                                               "Similar To Swatch", show_separator=False)
            else:
                self.options_window.set_option("similar_swatch", self.gen_random_palettes, OptionType.BUTTON,
                                               "Similar To Swatch", show_separator=False)
        else:
            self.options_window.remove_option("similar_swatch")

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        asyncme.run_or_none(self.gen_random_palettes)("random")
