import os.path

from lxml import etree

from sources.source import RemoteFile
from tasks.task import Task


class SvgColorReplace(Task):
    def __init__(self):
        self.element_types1 = ["path", "circle"]
        self.element_types2 = ["rect", "polygon", "line", "ellipse", "polyline"]
        self.new_fill_colors = {}
        self.new_stroke_colors = {}

    async def do_task(self, filepath) -> str:

        if self.is_active:
            svg, colors_fill, colors_stroke = await self.extract_color(filepath)
            for old_color, new_color in self.new_fill_colors.items():
                if old_color in colors_fill.keys():
                    self.change_color_of_elements(new_color, colors_fill[old_color], "fill")
            for old_color, new_color in self.new_stroke_colors.items():
                if old_color in colors_stroke.keys():
                    self.change_color_of_elements(new_color, colors_stroke[old_color], "stroke")

            xml = etree.tostring(svg, encoding="unicode")
            with open(filepath, mode="w+") as f:
                f.write(xml)

            # svg.write(filepath)

        return filepath

    async def extract_color(self, file):
        colors_fill = {}
        colors_stroke = {}
        if isinstance(file, RemoteFile):
            filepath = file.get_thumbnail()
            svg = etree.parse(filepath)
        elif os.path.isfile(file):
            svg = etree.parse(file)
        else:
            svg = etree.fromstring(file.strip())

        for element in svg.iter(tag=etree.Element):
            # Fill paths with no fill or stroke with black
            # so colors could be properly extracted
            if etree.QName(element).localname in self.element_types1 and \
                    ("fill" not in element.keys() or element.get("fill") is None) and \
                    "stroke" not in element.keys():
                element.attrib["fill"] = "#000000"
            elif etree.QName(element).localname in self.element_types2 and "style" in element.keys() \
                    and "fill:" not in element.attrib["style"]:
                style = element.attrib["style"]
                element.attrib["style"] = f"{style};fill:#000000"

            if etree.QName(element).localname in self.element_types2 and "style" in element.keys() \
                    and "fill:" in element.attrib["style"]:
                fill = list(filter(lambda s: "fill:" in s, element.get("style").split(";")))[0][5:]
            else:
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
            if new_color:
                if etree.QName(element).localname in self.element_types1:
                    element.attrib[attrib] = new_color
                elif etree.QName(element).localname in self.element_types2:
                    if element.get("style"):
                        styles = list(filter(lambda s: "fill:" not in s, element.get("style").split(";")))
                        styles.append(f"{attrib}:{new_color}")
                        element.attrib["style"] = ";".join(styles)
                    else:
                        element.attrib["style"] = f"{attrib}:{new_color}"
