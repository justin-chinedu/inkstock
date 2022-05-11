import json
import sys

from inkex.gui import asyncme
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW

from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType, ChangeReciever
from windows.view_change_listener import ViewChangeListener
from tasks.svg_color_replace import SvgColorReplace

sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from remote import RemoteFile, RemotePage, RemoteSource


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

    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name'][:7]}-joeschmoe"

    def get_thumbnail(self):
        name = self.name + ".svg"
        return self.remote.to_local_file(self.info["thumbnail"], name)

    def get_file(self):
        name = self.name + "file.svg"
        return self.remote.to_local_file(self.info["file"], name)


class JoeschmoePage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, url):
        super().__init__(remote_source, page_no)
        self.remote_source = remote_source
        self.url = url

    def get_page_content(self):
        info = {
            "name": self.remote_source.options["seed"],
            "file": self.url,
            "thumbnail": self.url,
            "license": ""
        }
        yield JoeschmoeIllustration(self.remote_source, info)


class JoeschmoeSource(RemoteSource, ViewChangeListener):
    name = "Joeschmoe"
    desc = "Joe Schmoes are colorful characters illustrated by Jon&amp;Jess that can be used as profile picture placeholders for live websites or design mock ups. "
    icon = "icons/joeschmoe.png"
    file_cls = JoeschmoeIllustration
    page_cls = JoeschmoePage
    is_default = False
    is_enabled = True
    items_per_page = 8
    reqUrl = "https://joeschmoe.io/api/v1{gender}{seed}"
    window_cls = JoeschmoeWindow

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)
        self.stroke_colors = {}
        self.fill_colors = {}
        self.query = ""
        self.results = []
        self.options = {}

        self.pix_manager = None
        self.color_ext = SvgColorReplace()
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("seed", None, OptionType.SEARCH, "Type name")
        self.options_window.set_option(
            "gender", ["all", "female", "male"], OptionType.DROPDOWN, "Choose gender")
        self.options_window.set_option("no_of_avatars", 1, OptionType.TEXTFIELD, "No of avatars")
        self.options_window.set_option("random", self.random_clicked, OptionType.BUTTON, "Generate random avatars")
        self.color_options = []

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
    def search(self, query, tags=None):
        query = query.lower().replace(' ', '_')
        self.query = query
        gender = self.options["gender"]
        if gender != "all":
            req_url = self.reqUrl.format(gender=f"/{gender}", seed=f"/{query}")
        else:
            req_url = self.reqUrl.format(gender="", seed=f"/{query}")
        self.window.clear_pages()
        self.window.show_spinner()
        self.get_page(0, req_url)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)

    def on_change(self, options):
        self.options = options
        if self.window and self.query != options["seed"]:
            self.search(self.query)

        if not self.window:
            return

        is_multi_view = self.window.results.is_multi_view()

        if is_multi_view:
            items = self.window.results.get_multi_view_displayed_data(only_selected=True)
        else:
            items = [self.window.results.get_single_view_displayed_data()[0]]
        for item in items:
            color_replace = None
            # Avoiding duplicate color replace tasks
            for task in item.data.tasks:
                if isinstance(task, SvgColorReplace):
                    color_replace = task
            if not color_replace:
                color_replace = SvgColorReplace()
                item.data.tasks.append(color_replace)
            color_replace.is_active = True
            color_replace.new_fill_colors = {}
            color_replace.new_stroke_colors = {}
            for fill, value in [(key.removeprefix("fill_"), value) for key, value in self.options.items() if
                                key.startswith("fill_")]:
                if value:
                    color_replace.new_fill_colors[fill] = value
            for stroke, value in [(key.removeprefix("stroke_"), value) for key, value in self.options.items() if
                                  key.startswith("stroke_")]:
                if value:
                    color_replace.new_stroke_colors[stroke] = value

            # thumbnail = self.pix_manager.get_pixbuf_for_task(item.data)
            # self.update_item(thumbnail, item)
        self.window.results.refresh_window()

    @asyncme.mainloop_only
    def file_selected(self, file: RemoteFile):
        for task in file.tasks:
            if isinstance(task, SvgColorReplace):
                return
        self.show_svg_colors(file)

    def show_svg_colors(self, file):
        file = file.get_thumbnail()
        _, fill_colors, stroke_colors = self.color_ext.extract_color(file)
        self.fill_colors = fill_colors
        self.stroke_colors = stroke_colors
        if fill_colors:
            if "set_fill" in self.options_window.options:
                self.options_window.attach_option("set_fill")
            else:
                self.options_window.set_option("set_fill", "Set fill colors", OptionType.TEXTVIEW, show_separator=True)

        for index, fill in enumerate(fill_colors.keys()):
            # Reusing existing option widgets instead of creating a new one
            if not len(self.color_options) >= index:
                self.color_options[index].view.set_color(fill)
                continue
            option = self.options_window.set_option("fill_" + fill, fill, OptionType.COLOR, f"Color {index + 1}",
                                                    show_separator=False)
            self.color_options.append(option)

        if stroke_colors:
            if "set_stroke" in self.options_window.options:
                self.options_window.attach_option("set_stroke")
            else:
                self.options_window.set_option("set_stroke", "Set stroke colors", OptionType.TEXTVIEW,
                                               show_separator=True)

        for index, stroke in enumerate(stroke_colors.keys()):
            # Reusing existing option widgets instead of creating a new one
            if not len(self.color_options) >= (index + len(fill_colors.keys())):
                self.color_options[index + len(fill_colors.keys())].view.set_color(stroke)
                continue
            option = self.options_window.set_option("stroke_" + stroke, stroke, OptionType.COLOR, f"Color {index + 1}",
                                                    show_separator=False)
            self.color_options.append(option)

    def on_view_changed(self, view):
        if self.window.results.is_multi_view():
            pass
        else:
            pass
