import os.path

from lxml import etree

from remote import RemoteFile
from tasks.task import Task


class SvgColorReplace(Task):
    def __init__(self):
        self.new_colors_fill = {}
        self.new_colors_stroke = {}

    def do_task(self, filepath) -> str:
        if self.is_active:
            svg, colors_fill, colors_stroke = self.extract_color(filepath)
            for old_color, new_color in self.new_colors_fill.items():
                if old_color in colors_fill.keys():
                    self.change_color_of_elements(new_color, colors_fill[old_color], "fill")
            for old_color, new_color in self.new_colors_stroke.items():
                if old_color in colors_stroke.keys():
                    self.change_color_of_elements(new_color, colors_stroke[old_color], "stroke")
            # name = os.path.basename(filepath) + "_color_extracted.svg"
            # path = os.path.join(os.path.dirname(filepath), name)
            svg.write(filepath)
            # return path
        return filepath

    def extract_color(self, file):
        colors_fill = {}
        colors_stroke = {}
        svg = etree.parse(file)
        for element in svg.iter(tag=etree.Element):
            fill = element.get("fill")
            if fill and fill != "none":
                colors_fill.setdefault(fill, [])
                colors_fill[fill].append(element)
            stroke = element.get("stroke")
            if stroke and stroke != "none":
                colors_stroke.setdefault(stroke, [])
                colors_stroke[stroke].append(element)
        return svg, colors_fill, colors_stroke

    def change_color_of_elements(self, new_color, elements, attrib):
        for element in elements:
            element.attrib[attrib] = new_color
