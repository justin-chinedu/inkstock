from core.constants import CACHE_DIR
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from sources.json_svg_source import JsonSvgIconsSource, JsonSvgWindow


class FeatherWindow(JsonSvgWindow):
    name = "feather_window"


class FeatherIconsSource(JsonSvgIconsSource):
    name = 'Feather Icons'
    desc = "Feather is a collection of simply beautiful open source icons. " \
           "Each icon is designed on a 24x24 grid with an emphasis on simplicity, " \
           "consistency, and flexibility."

    json_path = 'json/feather.json'
    window_cls = FeatherWindow


class SimpleWindow(JsonSvgWindow):
    name = "simple_window"


class SimpleIconsSource(JsonSvgIconsSource):
    name = 'Simple Icons'
    desc = "Over 2200 Free SVG icons for popular brands."
    icon = "icons/simpleicons-white.svg"
    json_path = 'json/simple_icons_compressed.json'
    json_is_compressed = True
    window_cls = SimpleWindow


class GameWindow(JsonSvgWindow):
    name = "game_window"


class GameIconsSource(JsonSvgIconsSource):
    name = 'Game Icons'
    desc = "An ever growing collection of free game icons"
    icon = "icons/gameicons.png"
    json_path = 'json/gameicons_compressed.json'
    json_is_compressed = True
    window_cls = GameWindow

    def get_pixmanger(self):
        pix = PixmapManager(CACHE_DIR, scale=0.3,
                            grid_item_height=200,
                            grid_item_width=200,
                            padding=120)

        pix.enable_aspect = False
        pix.preview_scaling = 0.3
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
        return pix


class BoxWindow(JsonSvgWindow):
    name = "box_window"


class BoxIconsSource(JsonSvgIconsSource):
    name = 'Box Icons'
    desc = "High Quality Web Icons and Simple Open Source icons" \
           " carefully crafted for designers and developers"
    icon = "icons/boxicons.png"
    json_path = 'json/boxicons.json'
    window_cls = BoxWindow


class FlatWindow(JsonSvgWindow):
    name = "flat_window"


class FlatIconsSource(JsonSvgIconsSource):
    name = 'Flat Color Icons'
    desc = "Feather is a collection of flat colorful icons by icons8"
    icon = "icons/icons8.png"
    json_path = 'json/flat_color.json'
    window_cls = FlatWindow

    def get_pixmanger(self):
        pix = PixmapManager(CACHE_DIR, scale=4,
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
        return pix


class OctWindow(JsonSvgWindow):
    name = "oct_window"


class OctIconsSource(JsonSvgIconsSource):
    name = 'Octicons'
    desc = "Octicons are a set of SVG icons built by GitHub for GitHub."
    icon = "icons/github.svg"
    json_path = 'json/octicons.json'
    window_cls = OctWindow


class RemixWindow(JsonSvgWindow):
    name = "remix_window"


class RemixIconsSource(JsonSvgIconsSource):
    name = 'Remix Icons'
    desc = "Remix Icon is a set of open source neutral style system " \
           "symbols elaborately crafted for designers and developers."
    icon = 'icons/remix.svg'
    json_path = 'json/remix.json'
    window_cls = RemixWindow


class BootstrapWindow(JsonSvgWindow):
    name = "bootstrap_window"


class BootstrapIconsSource(JsonSvgIconsSource):
    name = 'Bootstrap Icons'
    desc = "Free, high quality, open source icon library with over 1,600 icons. " \
           "Include them anyway you like, SVGs, SVG sprite, or web fonts"
    icon = "icons/bootstrap.png"
    json_path = 'json/bootstrap.json'
    window_cls = BootstrapWindow


class HeroWindow(JsonSvgWindow):
    name = "hero_window"


class HeroIconsSource(JsonSvgIconsSource):
    name = 'Hero Icons'
    desc = "A unique set of icons that are easy to customize with CSS"
    icon = 'icons/heroicons.png'
    json_path = 'json/heroicons.json'
    window_cls = HeroWindow
