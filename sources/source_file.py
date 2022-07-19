from core.constants import LICENSES
from tasks.task import Task


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
        self.text = "Form and function\n" \
                    "together create\n" \
                    "typographic excellence"
        self.font_size = 80

    def set_text(self, text: str):
        # TODO: format text to have max chars of 20
        pass
