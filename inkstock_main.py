from inkex import EffectExtension
from collections import defaultdict

import os
import gi

import inkex
from inkex.gui.app import GtkApp
from inkex.elements import (
    load_svg, Defs, NamedView, Metadata,
    SvgDocumentElement, StyleElement
)

from inkex.styles import Style

gi.require_version("Gtk", "3.0")


class Handler:
    def __init__(self, window) -> None:
        self.window = window


from windows.basic_window import BasicWindow
from windows.results_window import ResultsWindow
from windows.inkstocks_window import InkStocksWindow
from sources.undraw import UndrawWindow
from sources.pexels import PexelsWindow
from sources.unsplash import UnsplashWindow
from sources.pixabay import PixabayWindow


class InkStockApp(GtkApp):
    """Base App
    Add all windows to windows for it to be recognised"""
    app_name = "InkStock"
    ui_dir = "ui"
    windows = [InkStocksWindow,
               ResultsWindow, BasicWindow, UndrawWindow, PexelsWindow, UnsplashWindow, PixabayWindow]

    def __init__(self, start_loop=False, start_gui=True, **kwargs):
        self.ext = kwargs.setdefault("ext", None)
        super().__init__(start_loop, start_gui, **kwargs)


class InkstockExtension(EffectExtension):

    def merge_defs(self, defs):
        """Add all the items in defs to the self.svg.defs"""
        target = self.svg.defs
        for child in defs:
            if isinstance(child, StyleElement):
                continue  # Already appled in merge_stylesheets()
            target.append(child)

    def merge_stylesheets(self, svg):
        """Because we don't want conflicting style-sheets (classes, ids, etc) we scrub them"""
        elems = defaultdict(list)
        # 1. Find all styles, and all elements that apply to them
        for sheet in svg.getroot().stylesheets:
            for style in sheet:
                xpath = style.to_xpath()
                for elem in svg.xpath(xpath):
                    elems[elem].append(style)
                    # 1b. Clear possibly conflicting attributes
                    if '@id' in xpath:
                        elem.set_random_id()
                    if '@class' in xpath:
                        elem.set('class', None)
        # 2. Apply each style cascade sequentially
        for elem, styles in elems.items():
            output = Style()
            for style in styles:
                output += style
            elem.style = output + elem.style

    def import_svg(self, new_svg):
        """Import an svg file into the current document"""
        self.merge_stylesheets(new_svg)
        for child in new_svg.getroot():
            if isinstance(child, SvgDocumentElement):
                yield from self.import_svg(child)
            elif isinstance(child, StyleElement):
                continue  # Already applied in merge_stylesheets()
            elif isinstance(child, Defs):
                self.merge_defs(child)
            elif isinstance(child, (NamedView, Metadata)):
                pass
            else:
                yield child

    def import_from_file(self, filename):
        if not filename or not os.path.isfile(filename):
            return
        with open(filename, 'rb') as fhl:
            head = fhl.read(100)
            if b'<?xml' in head or b'<svg' in head:
                new_svg = load_svg(head + fhl.read())
                # Add each object to the container
                objs = list(self.import_svg(new_svg))

                if len(objs) == 1 and isinstance(objs[0], inkex.Group):
                    # Prevent too many groups, if item aready has one.
                    container = objs[0]
                else:
                    # Make a new group to contain everything
                    container = inkex.Group()
                    for child in objs:
                        container.append(child)

                # Retain the original filename as a group label
                container.label = os.path.basename(filename)
                # Apply unit transformation to keep things the same sizes.
                container.transform.add_scale(self.svg.unittouu(1.0)
                                              / new_svg.getroot().unittouu(1.0))

            else:
                container = self.import_raster(filename, fhl)

            self.svg.get_current_layer().append(container)

            # Make sure that none of the new content is a layer.
            for child in container.descendants():
                if isinstance(child, inkex.Group):
                    child.set("inkscape:groupmode", None)

    def effect(self):
        app = InkStockApp(start_loop=True, ext=self)

    @staticmethod
    def get_type(path, header):
        """Basic magic header checker, returns mime type"""
        # Taken from embedimage.py
        for head, mime in (
                (b'\x89PNG', 'image/png'),
                (b'\xff\xd8', 'image/jpeg'),
                (b'BM', 'image/bmp'),
                (b'GIF87a', 'image/gif'),
                (b'GIF89a', 'image/gif'),
                (b'MM\x00\x2a', 'image/tiff'),
                (b'II\x2a\x00', 'image/tiff'),
        ):
            if header.startswith(head):
                return mime
        return None


if __name__ == '__main__':
    InkStockApp(start_loop=True)
    # InkstockExtension().run()
