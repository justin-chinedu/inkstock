import json
import zlib
from abc import ABC, abstractmethod
from os.path import exists

from gi.repository import Gtk

from core.utils import asyncme
from sources.source import RemoteSource, sanitize_query
from sources.source_file import RemoteFile
from tasks.svg_color_replace import SvgColorReplace
from windows.basic_window import BasicWindow
from windows.options_window import OptionType, OptionsWindow, ColorOption
from windows.results_window import FlowBoxChildWithData
from windows.view_change_listener import ViewChangeListener


class SvgSource(RemoteSource, ViewChangeListener, ABC):
    json_path = None
    json_is_compressed = False
    default_svg_color = "#000000"
    default_search_query = "a"

    def __init__(self, cache_dir, import_manager):
        super().__init__(cache_dir, import_manager)
        self.icon_map = None
        self.query = ""
        self.last_selected_file = None
        self.color_ext = SvgColorReplace()
        self.default_color_task = None
        self.results = []
        self.options = {}
        self.search_color = None
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, f"Search {self.name}")
        self.search_color_option: ColorOption = self.options_window.set_option(
            "search_color", None, OptionType.COLOR, "Set default search color")
        self.search_color_option.set_color(self.default_svg_color)
        self.load_icon_map()

    def load_icon_map(self):
        # -----------------------
        if self.json_path:
            json_exists = exists(self.json_path)
            if json_exists:
                self.icon_map = self.read_map_file(self.json_path)
        # ---------

    @abstractmethod
    def get_page(self, page_no: int):
        pass

    @abstractmethod
    def search(self, query):
        pass

    def on_change(self, options):
        if not self.window:
            return

        query = sanitize_query(options["query"])

        if query and self.query != query:  # if search query changed
            self.query = query
            self.options = options
            self.search(self.query)
            return

        # proceed only when color values change
        if options["search_color"] != self.search_color:
            self.search_color = options["search_color"]
            s = SvgColorReplace()
            s.new_fill_colors = {self.default_svg_color: options["search_color"]}
            s.is_active = True
            self.default_color_task = s
            self.options = options
            return

        self.options = options

        multi_items, single_item, single_items = self.get_selected_items()

        # check for color changes in options and apply color replace task to item
        color_changes = [(key, value) for key, value in options.items()
                         if (key.startswith("fill") or key.startswith("stroke")) and value]

        if color_changes:
            add_color_changes_to_items(color_changes, multi_items)
            add_color_changes_to_items(color_changes, single_items)
            self.update_items_sequentially(single_items, single_item, multi_items)
            return

    def clear_color_options(self):
        self.options_window.remove_option("color_group")

    @asyncme.mainloop_only
    def show_svg_colors(self, file, fill_colors, stroke_colors):
        #  _, fill_colors, stroke_colors = self.color_ext.extract_color(file.get_thumbnail())

        # if color has been modified
        # should show modified color instead
        modified_fill_colors = {}
        modified_stroke_colors = {}
        for task in file.tasks:
            if isinstance(task, SvgColorReplace):
                modified_fill_colors = task.new_fill_colors
                modified_stroke_colors = task.new_stroke_colors
                break  # we should only have one color task

        widgets = []

        if fill_colors:
            widgets.append(
                self.options_window.set_option("set_fill", "<span>Set fill colors</span>", OptionType.TEXTVIEW,
                                               show_separator=False,
                                               attach=False))
        for index, fill in enumerate(fill_colors.keys()):
            displayed_fill = fill
            if fill in modified_fill_colors.keys():
                # TODO: Maybe try and convert hex to rgba before setting chooser color to support alpha
                # i trimmed off alpha because Gtk color chooser doesn't support alpha in hex
                displayed_fill = modified_fill_colors[fill] # show modified fill instead of original fill
            color_option = self.options_window.set_option("fill_" + fill, displayed_fill, OptionType.COLOR,
                                                          f"Color {index + 1}",
                                                          attach=False, show_separator=False)
            widgets.append(color_option)

        if stroke_colors:
            widgets.append(
                self.options_window.set_option("set_stroke", "<span>Set stroke colors</span>", OptionType.TEXTVIEW,
                                               show_separator=False, attach=False))
        for index, stroke in enumerate(stroke_colors.keys()):
            displayed_stroke = stroke
            if stroke in modified_stroke_colors.keys():
                # TODO: Maybe try and convert hex to rgba before setting chooser color to support alpha
                # trim off alpha because Gtk color chooser doesn't support alpha in hex
                displayed_stroke = modified_stroke_colors[stroke]
            color_option = self.options_window.set_option("stroke_" + stroke, displayed_stroke, OptionType.COLOR,
                                                          f"Color {index + 1}",
                                                          attach=False, show_separator=False)
            widgets.append(color_option)
        group = self.options_window.set_option("color_group", widgets, OptionType.GROUP, "Change colors",
                                               show_separator=False)
        group.view.show_all()

    @asyncme.mainloop_only
    def file_selected(self, file: RemoteFile):
        if file != self.last_selected_file:
            self.last_selected_file = file
            self.clear_color_options()

            def cb(result, error):
                if error:
                    print(f"Error occurred in task: {error}")
                if result:
                    svg, fill_colors, stroke_colors = result
                    self.show_svg_colors(file, fill_colors, stroke_colors)

            self.add_task_to_queue(self.color_ext.extract_color, cb, file)

    def files_selection_changed(self, files: list[RemoteFile]):
        super().files_selection_changed(files)
        # multiple file selection could occur without triggering
        # a single selection

        if files and self.window.results.is_multi_view():  # List would be cleared on search, so we avoid index error
            first_item = files[0]
            self.file_selected(first_item)
        else:
            self.clear_color_options()  # if list is empty ( when a new search is made )

    @classmethod
    def read_map_file(cls, path):
        with open(path, mode='rb') as f:
            if cls.json_is_compressed:
                m = json.loads(zlib.decompress(f.read()))
            else:
                m = json.load(f)
            s = m
            if type(m) is dict:
                s = dict(sorted(m.items()))
        return s

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        search_entry: Gtk.SearchEntry = self.options_window.options["query"].entry
        search_entry.set_text(self.default_search_query)
        asyncme.run_or_none(self.search)(self.default_search_query)

    def on_view_changed(self, view):
        pass


def add_color_changes_to_items(color_changes: list[tuple], items: list[FlowBoxChildWithData]):
    if not items:
        return

    fill_color_changes = list(filter(lambda x: x[0].startswith("fill"), color_changes))
    stroke_color_changes = list(filter(lambda x: x[0].startswith("stroke"), color_changes))

    color_replace = SvgColorReplace()
    color_replace.is_active = True

    # update fill colors for color replace task
    for color in fill_color_changes:
        old_color = color[0].removeprefix("fill_")
        new_color = color[1]
        color_replace.new_fill_colors[old_color] = new_color

    # update stroke colors for color replace task
    for color in stroke_color_changes:
        old_color = color[0].removeprefix("stroke_")
        new_color = color[1]
        color_replace.new_stroke_colors[old_color] = new_color

    for item in items:
        file: RemoteFile = item.data
        # avoid adding duplicate color replace task
        for task in file.tasks:
            if isinstance(task, SvgColorReplace):
                file.tasks.remove(task)
        # the color task has to be the first item before other
        # tasks are applied to svg
        file.tasks.insert(0, color_replace)



