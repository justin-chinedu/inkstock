#
# Copyright 2022 Justin Chinedu <chinedujustin491@gmail.com>
# Copyright 2022 Simon Duerr <dev@simonduerr.eu>
# Copyright 2021 Martin Owens <doctormo@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>
#
import re

from core.constants import CACHE_DIR, LICENSES
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from core.utils import asyncme
from sources.source import RemoteSource, sanitize_query, SourceType
from sources.source_file import RemoteFile
from sources.source_page import RemotePage, NoResultsPage
from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType


class ReactomeWindow(BasicWindow):
    name = "reactome_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmap_manager(self):
        pix = PixmapManager(CACHE_DIR, scale=0.7,
                            grid_item_height=250,
                            grid_item_width=250,
                            padding=120)

        pix.enable_aspect = False
        pix.preview_scaling = 0.5
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
        self.source.pix_manager = pix
        return pix


class ReactomeFile(RemoteFile):
    def __init__(self, source, info):
        super().__init__(source, info)
        self.format = self.info["file"].split(".")[-1]
        self.name = f"{self.info['name']}".replace(f".{self.format}", "")
        self.file_name = self.name + "-reactome." + self.format
        self.show_name = True


class ReactomePage(RemotePage):
    file_url = "https://reactome.org/icon/{stId}.svg"
    icon_url = "https://reactome.org/icon/{stId}.png"
    all_licence = "cc-by-sa-4.0"
    TAG_REX = re.compile(r'<[^<]+?>')

    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source

    def get_page_content(self):
        for entry in self.results:
            info = {
                'id': entry['dbId'],
                'name': self.TAG_REX.sub('', entry['name']),
                'author': 'Reactome/' + entry.get('iconDesignerName', "Unknown"),
                'summary': self.TAG_REX.sub('', entry.get('summation', '')),
                'created': None,  # No data
                'popularity': 0,  # No data
                'thumbnail': self.icon_url.format(**entry),
                'file': self.file_url.format(**entry),
                'license': self.all_licence,
            }

            file = ReactomeFile(self.remote_source, info)
            yield file


class ReactomeSource(RemoteSource):
    name = 'Reactome'
    desc = 'Reactome is a free, open-source, curated and peer-reviewed pathway database'
    icon = "icons/reactome.png"
    source_type = SourceType.ILLUSTRATION
    file_cls = ReactomeFile
    page_cls = ReactomePage
    is_default = False
    is_enabled = True
    options_window_width = 300
    items_per_page = 18
    window_cls = ReactomeWindow

    search_url = "https://reactome.org/ContentService/search/query"

    def __init__(self, cache_dir, import_manager):
        super().__init__(cache_dir, import_manager)

        self.query = ""
        self.results = []
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, f"Search {self.name}")
        self.options_window.set_option("info", "", OptionType.TEXTVIEW, show_separator=False)

    def get_page(self, page_no: int):
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            self.current_page = page_no
            page = ReactomePage(self, page_no, results)
            self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.window.show_spinner()

        params = {
            "query": query,
            "types": "Icon",
            "cluster": "true",
            "Start row": 0,
            "rows": 100,
        }

        response = {}
        try:
            response = self.session.get(self.search_url, params=params).json()
        except Exception:
            pass

        if 'messages' in response and 'No entries' in response['messages'][0]:
            self.window.add_page(NoResultsPage(query))
            return

        for cats in response.get('results', []):
            self.results.extend(cats['entries'])

        if not self.results:
            self.window.add_page(NoResultsPage(query))
        else:
            self.get_page(0)

    def on_change(self, options):
        self.query = sanitize_query(options["query"])
        self.options = options
        if self.window and self.query:
            self.search(self.query)
            return

    def file_selected(self, file: RemoteFile):
        super().file_selected(file)
        info = file.info
        text = f'<span  size="large" weight="normal" >Illustration by</span>\n\n' + \
               f'<span  size="large" weight="bold" >{info["author"]}</span>\n\n' + \
               f'<span  size="large" weight="normal" >{info["name"]}</span>\n\n' + \
               f'<span  size="medium" weight="normal" >Available under the {LICENSES[info["license"]]["name"]} license, ' \
               f'<a href="{LICENSES[info["license"]]["url"]}">More Info</a></span>'
        text.replace("&", "&amp;")
        self.options_window.options["info"].view.set_markup(text)
