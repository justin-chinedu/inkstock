import os
import random
import uuid
from typing import Tuple

from gi.repository.GObject import Object

from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_CROP, SIZE_ASPECT_GROW
from core.utils import asyncme
from sources.source import SourceType, RemoteSource
from sources.source_file import HumaansSvg, RemoteFile
from sources.source_page import RemotePage
from windows.basic_window import BasicWindow
from windows.options_window import OptionType, OptionsWindow, OptionsChangeListener
from windows.view_change_listener import ViewChangeListener

from gi.repository import Gtk


class HumaansWindow(BasicWindow):
    name = "humaans_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmap_manager(self):
        pix = PixmapManager(CACHE_DIR, scale=1,
                            grid_item_height=300,
                            grid_item_width=300,
                            padding=50)

        pix.enable_aspect = False
        pix.single_preview_scale = 0.8
        pix.preview_scaling = 1
        pix.preview_padding = 30
        pix.preview_item_width = 100
        pix.preview_item_height = 100
        pix.preview_aspect_ratio = SIZE_ASPECT_GROW
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


class HumaansFile(RemoteFile):
    def __init__(self, source, info, svg: HumaansSvg):
        super().__init__(source, info)
        self.humaans_svg = svg
        self.name = self.info["name"]
        self.id = str(hash(self.info["id"] + self.name))  # overrode implementation because info["file"] is empty
        self.file_name = f"{self.name}-{self.id}-humaans" + ".svg"

    def get_thumbnail(self):
        file_path = os.path.join(self.source.cache_dir, self.file_name)
        self.humaans_svg.save_to_file(file_path)
        return self.file_name

    def get_file(self):
        return "file://" + os.path.join(self.source.cache_dir, self.get_thumbnail())


class HumaansPage(RemotePage):

    def __init__(self, remote_source, page_no: int):
        super().__init__(remote_source, page_no)

    def get_page_content(self):
        for i in range(self.remote_source.items_per_page):
            template = random.choice(self.remote_source.templates)
            body = random.choice(self.remote_source.bodies)
            head = random.choice(self.remote_source.heads_front)
            scene = random.choice(self.remote_source.scenes)
            bottom = random.choice(
                random.choice([self.remote_source.bottoms_standing, self.remote_source.bottoms_sitting]))
            b_object = random.choice(self.remote_source.objects_seats)

            h = HumaansSvg(template)
            h.change_part(part=body, name="body")
            h.change_part(part=head, name="head")
            h.change_part(part=bottom, name="bottom")
            h.change_part(part=b_object, name="object")
            h.add_scene(scene)

            _id = str(uuid.uuid4())
            info = {
                "id": _id,
                "name": h.title.text.split("/")[-1],
                "author": "Pablo Stanley",
                "thumbnail": "",
                "license": "cc-o",
                "file": "",
            }

            yield HumaansFile(self.remote_source, info, h)


def get_image_row() -> tuple[Gtk.Box, Gtk.Image, Gtk.Label]:
    builder = Gtk.Builder()
    builder.add_from_file("ui/image_row.glade")
    row = builder.get_object("image_row")
    image = builder.get_object("image")
    label = builder.get_object("label")
    return row, image, label


class HumaansSource(RemoteSource, OptionsChangeListener, ViewChangeListener):
    name = 'Humaans'
    desc = "Mix-&amp;-match illustrations of people with a design library"
    icon = "icons/humaans.svg"
    source_type = SourceType.ILLUSTRATION
    file_cls = HumaansFile
    page_cls = HumaansPage
    is_default = False
    is_enabled = True
    options_window_width = 300
    items_per_page = 12
    window_cls = HumaansWindow

    def __init__(self, cache_dir, import_manager):
        super().__init__(cache_dir, import_manager)
        self.last_selected_part_file = None
        self.select_parts = None
        self.last_selected_file = None
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("random", self._get_home, OptionType.BUTTON, "Generate")
        self.options = {}
        self.parts = {
            "Heads": [],
            "Bodies": [],
            "Bottoms (Sitting)": [],
            "Bottoms (Standing)": [],
            "Scenes": [],
            "Objects": []
        }
        self.parts_pix_manager = PixmapManager(cache_dir)
        self.select_parts = self.options_window.set_option("parts_select", list(self.parts.keys()), OptionType.DROPDOWN,
                                                           "Select Part", allow_multiple=False)
        self.last_selected_part = None
        self.last_selected_file_colors = None
        self.last_color_options = {}

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self._get_home(None)

    def get_page(self, page_no: int):
        page = HumaansPage(self, page_no)
        self.window.add_page(page)

    def search(self, query):
        pass

    def on_view_changed(self, view):
        pass

    def on_change(self, options):
        if not self.window:
            return
        print(options)

        if "parts_select" in options:
            part = options["parts_select"]
            if self.last_selected_part != part:
                self.last_selected_part = part
                self._show_part(part)

                return

        file = options.get("parts_list")
        if file and self.last_selected_part_file != file:
            self.last_selected_part_file = file
            part = self.last_selected_part
            if self.last_selected_file:
                svg: HumaansSvg
                multi_items, single_item, single_items = self.get_selected_items()
                if not single_item:
                    svg = multi_items[0].data.humaans_svg
                else:
                    svg = self.last_selected_file.humaans_svg
                if part == "Heads":
                    svg.change_part(file, "head")
                elif part == "Bodies":
                    svg.change_part(file, "body")
                elif part == "Scenes":
                    svg.add_scene(file)
                elif part == "Objects":
                    svg.change_part(file, "object")
                elif "Bottoms" in part:
                    svg.change_part(file, "bottom")
                else:
                    return

                self.refresh_selected_items()
                self._show_svg_color(svg)
            return

        color_options = {k: v for k, v in options.items() if "#" in k}
        for key, value in color_options.items():
            if value and value != self.last_color_options.get(key):
                if self.last_selected_file_colors:
                    part = key.split("|")[0]
                    sub_part_title = key.split("|")[1]
                    init_hex_color = key.split("|")[2]
                    part_colors = self.last_selected_file_colors[part]
                    part_colors[f"{sub_part_title}|{init_hex_color}"].attrib["fill"] = value
                    self.refresh_selected_items()
        self.last_color_options = color_options

    def update_items_sequentially(self, single_items, single_item, multi_items):
        if single_item:
            self.window.results.singleview.multi_items_to_update.update(multi_items)
            thumbnail = single_item.data.get_thumbnail()
            pixbuf = self.pix_manager.get_pixbuf(thumbnail, self.pix_manager.pref_width, self.pix_manager.pref_height,
                                                 self.pix_manager.padding, self.pix_manager.single_preview_scale,
                                                 SIZE_ASPECT_GROW, return_pixbuf=True)
            self.window.results.singleview.set_image(pixbuf)
            pixbuf_path = self.pix_manager.get_pixbuf(thumbnail, self.pix_manager.preview_item_width,
                                                      self.pix_manager.preview_item_height,
                                                      self.pix_manager.preview_padding,
                                                      self.pix_manager.preview_scaling,
                                                      self.pix_manager.preview_aspect_ratio,
                                                      thumbnail=True)
            self.update_item(pixbuf_path, single_items[0])
        else:
            for item in multi_items:
                self.pix_manager.get_pixbuf_for_type(item.data, "multi", self.update_item, item)

    def _show_part(self, part):
        part_files = self.parts.get(part)
        parts_widgets = []

        for file in part_files:
            row, image, label = get_image_row()
            pixbuf = self.parts_pix_manager.get_pixbuf(file, 100, 100, 0, 0.7, SIZE_ASPECT_GROW, True)
            image.set_from_pixbuf(pixbuf)
            label.set_text(os.path.basename(file).replace(".svg", ""))
            parts_widgets.append((row, file))
        select_option = self.options_window.set_option("parts_list", parts_widgets, OptionType.SELECT,
                                                       f"Choose {part}", allow_multiple=False)
        self.options_window.reorder_option("parts_list", 2)
        # select_option.show_max_rows(5)

    def _show_svg_color(self, svg: HumaansSvg):
        self.last_selected_file_colors = svg.get_colors()
        for part, subpart in self.last_selected_file_colors.items():
            colors = []
            for key in subpart.keys():
                title = key.split("|")[0]
                hex_color = key.split("|")[1]
                color_option = self.options_window.set_option(f"{part}|{title}|{hex_color}", hex_color,
                                                              OptionType.COLOR,
                                                              title.split("/")[-1], attach=False, show_separator=False)
                colors.append(color_option)
            self.options_window.set_option(f"{part}_color_group", colors, OptionType.GROUP,
                                           f"Change {part} colors", allow_multiple=False)

    @asyncme.mainloop_only
    def file_selected(self, file: RemoteFile):
        if file != self.last_selected_file:
            self.last_selected_file = file
            svg: HumaansSvg = file.humaans_svg
            self._show_svg_color(svg)

    @asyncme.run_or_none
    def _get_home(self, _):
        self.window.clear_pages()
        self.window.show_spinner()
        self._fetch_resources()
        self.last_selected_part = "Heads"
        asyncme.mainloop_only(self._show_part)("Heads")
        self.get_page(0)

    def _fetch_resources(self):
        self.templates = [os.path.join("assets/Humaans/Templates", f) for f in
                          os.listdir("assets/Humaans/Templates")]
        self.bodies = [os.path.join("assets/Humaans/Single Pieces/Body", f) for f in
                       os.listdir("assets/Humaans/Single Pieces/Body")]
        self.bottoms_sitting = [os.path.join("assets/Humaans/Single Pieces/Bottom/Sitting", f) for f in
                                os.listdir("assets/Humaans/Single Pieces/Bottom/Sitting")]
        self.bottoms_standing = [os.path.join("assets/Humaans/Single Pieces/Bottom/Standing", f) for f in
                                 os.listdir("assets/Humaans/Single Pieces/Bottom/Standing")]
        self.heads_front = [os.path.join("assets/Humaans/Single Pieces/Head/Front", f) for f in
                            os.listdir("assets/Humaans/Single Pieces/Head/Front")]
        self.objects_seats = [os.path.join("assets/Humaans/Single Pieces/Objects/Seat", f) for f in
                              os.listdir("assets/Humaans/Single Pieces/Objects/Seat")]
        self.scenes = [os.path.join("assets/Humaans/Single Pieces/Scene", f) for f in
                       os.listdir("assets/Humaans/Single Pieces/Scene")]

        self.parts["Heads"] = self.heads_front
        self.parts["Bodies"] = self.bodies
        self.parts["Bottoms (Sitting)"] = self.bottoms_sitting
        self.parts["Bottoms (Standing)"] = self.bottoms_standing
        self.parts["Scenes"] = self.scenes
        self.parts["Objects"] = self.objects_seats
