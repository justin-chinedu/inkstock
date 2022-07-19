import os
import uuid

from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_CROP
from core.utils import asyncme
from core.utils.color_palette import gen_svg_palette, gen_random_svg_palette
from sources.source import RemoteFile, RemotePage, RemoteSource, SourceType
from tasks.svg_color_replace import SvgColorReplace
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
                            padding=5)

        pix.enable_aspect = False
        pix.preview_scaling = 7
        pix.preview_padding = 30
        pix.preview_aspect_ratio = SIZE_ASPECT_CROP
        pix.preview_item_height = 100
        pix.preview_item_width = 150
        pix.style = """.{id}{{
            background-color: white;
            background-size: cover;
            background-repeat: no-repeat;
            background-origin: content-box;
            background-image: url("{url}");
            }}
        """
        self.source.pix_manager = pix
        return pix


class ColorMindPalette(RemoteFile):
    def __init__(self, source, info, preferred_swatch_colors=None):
        super().__init__(source, info)
        if preferred_swatch_colors is None:
            preferred_swatch_colors = []
        self.preferred_swatch_colors = preferred_swatch_colors
        self.name = f"{self.info['name']}-color-mind"
        self.id = str(hash(self.info["id"] + self.name))  # overrode implementation because info["file"] is empty
        self.file_name = self.name + ".svg"

    def get_thumbnail(self):
        if not self.info["thumbnail"]:
            if not self.preferred_swatch_colors:
                svg = gen_random_svg_palette()
            else:
                svg = gen_svg_palette(pref_colors=self.preferred_swatch_colors[:2])
            self.info["thumbnail"] = svg
            self.info["file"] = svg

        file_path = os.path.join(self.source.cache_dir, self.file_name)
        with open(file_path, mode="w+") as f:
            f.writelines(self.info["thumbnail"])
        return self.file_name

    def get_file(self):
        file_path = os.path.join(self.source.cache_dir, self.file_name)
        with open(file_path, mode="w+") as f:
            f.writelines(self.info["file"])
        return "file://" + file_path


class ColorMindPalettesPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, preferred_swatch_colors=None):
        super().__init__(remote_source, page_no)
        if preferred_swatch_colors is None:
            preferred_swatch_colors = []
        self.preferred_swatch_colors = preferred_swatch_colors
        self.remote_source = remote_source
        self.default_color_task = None

    def get_page_content(self):

        for svg in range(self.remote_source.items_per_page):
            ID = str(uuid.uuid4())
            info = {
                "id": ID,
                "name": "swatch" + ID,
                "author": "Color Mind",
                "thumbnail": "",
                "license": "",
                "summary": "",
                "file": "",
            }

            palette = ColorMindPalette(self.remote_source, info, preferred_swatch_colors=self.preferred_swatch_colors)

            if self.default_color_task:
                palette.tasks.append(self.default_color_task)
            yield palette


def hex_to_rgb(hex_color: str):
    h = hex_color.lstrip('#')
    rgb = list(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return rgb


class ColorMindPalettesSource(RemoteSource, ViewChangeListener):
    name = 'Color Mind'
    desc = "ColorMind is a color scheme generator that uses deep learning." \
           " It can learn color styles from photographs, movies, and popular art."
    icon = "icons/color_mind.svg"
    source_type = SourceType.SWATCH
    file_cls = ColorMindPalette
    page_cls = ColorMindPalettesPage
    is_default = False
    is_enabled = True
    options_window_width = 300
    items_per_page = 12
    window_cls = ColorMindWindow

    def __init__(self, cache_dir, import_manager):
        super().__init__(cache_dir, import_manager)
        self.last_selected_file = None
        self.color_ext = SvgColorReplace()
        self.default_color_task = None
        self.results = []
        self.preferred_swatch_colors = []
        self.options = {}
        self.swatch_color = None
        self.options_window = OptionsWindow(self)
        self.search_color_option: ColorOption = self.options_window.set_option(
            "swatch_color", "#ffffff", OptionType.COLOR, "Swatch from color")
        self.options_window.set_option("random", self.gen_random_palettes, OptionType.BUTTON,
                                       "Random", show_separator=False)

    def get_page(self, page_no: int):
        page = ColorMindPalettesPage(remote_source=self, page_no=page_no,
                                     preferred_swatch_colors=self.preferred_swatch_colors)
        page.default_color_task = self.default_color_task
        self.window.add_page(page)

    def gen_random_palettes(self, _):
        self.window.clear_pages()
        self.window.show_spinner()
        self.preferred_swatch_colors = None
        self.get_page(0)

    def gen_swatches_from_swatch(self, _):
        multi_items = []
        single_items = []
        single_item = None
        results_is_multi_view = self.window.results.is_multi_view()
        if results_is_multi_view:
            items = self.window.results.get_multi_view_displayed_data(only_selected=True)
            multi_items.extend(items)
            single_item = multi_items[0]  # only supports one item at the moment
        else:
            items = self.window.results.singleview.list.get_selected_children()
            single_items.extend(items)
            single_item = items[0]

        svg_data: str = single_item.data.info["thumbnail"]

        def cb(result, error):
            if error:
                print(f"Error occurred in task(Color Extraction): {error}")
            if result:
                svg, fill_colors, stroke_colors = result
                self.preferred_swatch_colors = list(map(lambda color: hex_to_rgb(color), fill_colors.keys()))
                self.window.clear_pages()
                self.window.show_spinner()
                self.get_page(0)

        self.add_task_to_queue(self.color_ext.extract_color, cb, svg_data)

    @asyncme.run_or_none
    def search(self, query):
        pass

    def on_change(self, options):
        if not self.window:
            return

        # proceed only when color values change
        if options["swatch_color"] != self.swatch_color:
            self.swatch_color = options["swatch_color"]
            self.options = options
            self.preferred_swatch_colors = list(map(lambda color: hex_to_rgb(color), [self.swatch_color]))
            self.window.clear_pages()
            self.window.show_spinner()
            self.get_page(0)
            return

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
                self.options_window.set_option("similar_swatch", self.gen_swatches_from_swatch, OptionType.BUTTON,
                                               "Similar To Swatch", show_separator=False)
            else:
                self.options_window.set_option("similar_swatch", self.gen_swatches_from_swatch, OptionType.BUTTON,
                                               "Similar To Swatch", show_separator=False)
        else:
            self.options_window.remove_option("similar_swatch")

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        asyncme.run_or_none(self.gen_random_palettes)("random")
