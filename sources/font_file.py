from sources.source import RemoteFile


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
