from core.constants import LICENSES
from tasks.task import Task
from lxml import etree
from lxml.etree import ElementTree, Element


class RemoteFile:
    def get_thumbnail(self):
        return self.source.to_local_file(self.info["thumbnail"], self.file_name)

    def get_file(self):
        return self.info["file"]

    def __init__(self, source, info):
        # name to be displayed
        self.name = None
        # name to be saved as including extension
        self.file_name = None
        for field in ("name", "thumbnail", "license", "file"):
            if field not in info:
                raise ValueError(f"Field {field} not provided in RemoteFile package")
        self.info = info
        self.id = hash(self.info["file"])
        self.source = source
        self.tasks: list[Task] = []
        self.show_name = False

    @property
    def license(self):
        return self.info["license"]

    @property
    def license_info(self):
        return LICENSES.get(self.license, {
            "name": "Unknown",
            "url": self.info.get("descriptionurl", ""),
            "modules": [],
            "overlay": "unknown.svg",
        })

    @property
    def author(self):
        return self.info["author"]


class NoMoreResultsFile:
    def __init__(self, query: str):
        self.message = f'<span  size="large" weight="normal" >No search results for</span>\n' + \
                       f'<span  size="large" weight="bold" >{query.replace("%20", " ")}</span>\n'


class FontFile(RemoteFile):
    def __init__(self, source, info):
        super().__init__(source, info)
        self.line_spacing = 40
        self.color = "#383838"
        self.bg_color = "#ffffff"
        self.text = "Type is what meaning\n" \
                    "looks like."
        self.font_size = 80

    def set_text(self, text: str):
        # TODO: format text to have max chars of 20
        pass


class HumaansSvg:
    def __init__(self, template: str):
        self.template = template
        self._svgTree: ElementTree = etree.parse(template)
        self.svg = self._svgTree.getroot()
        self._is_standing = False
        self.colors = {}
        self.object = None
        self._parse_svg(self._svgTree)
        self._add_bg_element()
        self.scene = None
        self._width = self.svg.attrib["width"].replace("px", "")
        self._height = self.svg.attrib["height"].replace("px", "")
        self._transform = self._trans_group.attrib.get("transform")
        self.file_name = "/sdcard/test.svg"

    def get_colors(self, ):
        parts = {"Head": self.head, "Body": self.body, "Bottom": self.bottom, "Background": self.bg}
        self.colors.clear()
        for name, part in parts.items():
            self.colors.setdefault(name, {})
            for e in part.iter(tag=etree.Element):
                _id = e.attrib.get("id")
                _fill = e.attrib.get("fill")
                if _id and _fill:
                    self.colors[name][f"{_id}|{_fill}"] = e
        return self.colors

    def _add_bg_element(self):
        bg_attrib = {
            "id": "bg",
            "width": "100%",
            "height": "100%",
            "fill": "#ffffff"
        }
        self.bg = etree.Element("rect", attrib=bg_attrib)
        self.svg.insert(3, self.bg)

    def remove_scene(self):
        if self.scene is not None:
            self.svg.remove(self.scene)
            self.svg.attrib["width"] = f"{self._width}px"
            self.svg.attrib["height"] = f"{self._height}px"
            self.svg.attrib["viewBox"] = f"0 0 {self._width} {self._height}"
            if self._transform:
                self._trans_group.attrib["transform"] = self._transform
            else:
                self._trans_group.attrib.pop("transform")
            self.scene = None

    def add_scene(self, scene: str):
        scene_elem = None
        part_svg: ElementTree = etree.parse(scene)
        width = part_svg.getroot().attrib["width"].replace("px", "")
        height = part_svg.getroot().attrib["height"].replace("px", "")
        for element in part_svg.iter(tag=etree.Element):
            if etree.QName(element).localname == "g" and "Scene" in element.attrib["id"]:
                scene_elem = element

        i = 0
        for index, e in enumerate(list(self.svg)):
            _id = e.attrib.get("id")
            if _id and "Scene/" in _id:
                self.scene = e
                i = index
                break
        if self.scene is not None and scene_elem is not None:
            self.svg.remove(self.scene)
            self.svg.insert(i, scene_elem)
        else:
            self.scene = scene_elem
            self.svg.insert(4, scene_elem)
        self.svg.attrib["width"] = f"{width}px"
        self.svg.attrib["height"] = f"{height}px"
        self.svg.attrib["viewBox"] = f"0 0 {width} {height}"
        self._reposition()

    def _reposition(self):
        if self._is_standing:
            self._trans_group.attrib[
                "transform"] = f"translate({int(self._width) / 2} {int(self._height) / 4}) scale(1.2)"
        else:
            self._trans_group.attrib[
                "transform"] = f"translate({int(self._width) / 2} {int(self._height) / 2}) scale(1.2)"

    def save_to_file(self, filepath):
        xml = etree.tostring(self._svgTree, encoding="unicode")
        with open(filepath, mode="w+") as f:
            f.write(xml)
        # self._svgTree.write(filename)

    def _parse_svg(self, svg: ElementTree):
        for element in svg.iter(tag=etree.Element):
            if etree.QName(element).localname == "title":
                self.title = element
            elif etree.QName(element).localname == "desc":
                self.desc = element
                self.desc.text = "Generated by InkStock"
            elif etree.QName(element).localname == "g" and "humaaans" in element.attrib["id"]:
                self._style_group = element
                self._trans_group = element[0]
                for part in list(self._trans_group):
                    if "Head" in part.attrib["id"]:
                        self.head = part
                    elif "Body" in part.attrib["id"]:
                        self.body = part
                    elif "Bottom" in part.attrib["id"]:
                        if "Standing/" in part.attrib["id"]:
                            self._is_standing = True
                        elif "Sitting/" in part.attrib["id"]:
                            self._is_standing = False
                        self.bottom = part
                        for bottom_part in list(self.bottom):
                            _id = bottom_part.attrib.get("id")
                            if _id and "Object" in _id:
                                self.object = bottom_part
                                break
                break

    def change_part(self, part: str, name: str):
        part_svg: ElementTree = etree.parse(part)
        for element in part_svg.iter(tag=etree.Element):
            if etree.QName(element).localname == "g" and name.lower() in element.attrib["id"].lower():
                p = getattr(self, name.lower(), None)
                if p is not None:
                    for elem in p:
                        p.remove(elem)
                    p.extend([e for e in element])
                    if name == "bottom":
                        self.object = None
                        for bottom_part in list(p):
                            _id = bottom_part.attrib.get("id")
                            if _id and "Object" in _id:
                                self.object = bottom_part
                                break
                    if "Standing/" in element.attrib["id"]:
                        self._is_standing = True
                        self._width = 380
                        self._height = 480
                        if self.scene is not None:
                            self._reposition()
                        else:
                            self.svg.attrib["viewBox"] = "0 0 380 480"
                            self.svg.attrib["width"] = "380px"
                            self.svg.attrib["height"] = "480px"
                    elif "Sitting/" in element.attrib["id"]:
                        self._is_standing = False
                        self._width = 380
                        self._height = 400
                        if self.scene is not None:
                            self._reposition()
                        else:
                            self.svg.attrib["viewBox"] = "0 0 380 400"
                            self.svg.attrib["width"] = "380px"
                            self.svg.attrib["height"] = "400px"

                    p.attrib["id"] = element.attrib["id"]
                    break
