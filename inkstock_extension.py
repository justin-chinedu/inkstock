import os
from base64 import encodebytes
from collections import defaultdict

import inkex
from inkex import EffectExtension, Image, Style
from inkex.elements import (
    load_svg, Defs, NamedView, Metadata,
    SvgDocumentElement, StyleElement
)
from inkstock import InkStockApp


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

    def import_raster(self, filename, handle):
        """Import a raster image"""
        # Don't read the whole file to check the header
        handle.seek(0)
        file_type = self.get_type(filename, handle.read(10))
        handle.seek(0)

        if file_type:
            # Future: Change encodestring to encodebytes when python3 only
            node = Image()
            node.label = os.path.basename(filename)
            node.set('xlink:href', 'data:{};base64,{}'.format(
                file_type, encodebytes(handle.read()).decode('ascii')))
            return node

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
        InkStockApp(start_loop=True, ext=self)

    @staticmethod
    def get_type(path, header):
        """Basic magic header checker, returns mime display_type"""
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
    InkstockExtension().run()
