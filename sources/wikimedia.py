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

from core.constants import CACHE_DIR, LICENSES
from core.gui.pixmap_manager import PixmapManager, SIZE_ASPECT_GROW
from core.utils import asyncme
from sources.source import RemoteSource, sanitize_query, SourceType
from sources.source_file import RemoteFile
from sources.source_page import RemotePage, NoResultsPage
from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType


class WikiMediaWindow(BasicWindow):
    name = "wikimedia_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmap_manager(self):
        pix = PixmapManager(CACHE_DIR, scale=3,
                            grid_item_height=250,
                            grid_item_width=250,
                            padding=120)

        pix.enable_aspect = False
        pix.preview_scaling = 1
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


class WikiMediaFile(RemoteFile):
    def __init__(self, source, info):
        super().__init__(source, info)
        self.format = self.info["file"].split(".")[-1]
        self.name = f"{self.info['name']}".replace(f".{self.format}", "")
        self.file_name = self.name + "-wiki." + self.format
        self.show_name = True


class WikiMediaPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source

    def get_page_content(self):
        for item in self.results:
            img = item["imageinfo"][0]
            # get standard licenses
            # for non-standard licenses we have to get the ShortName and provide the url to the resource
            try:
                license = img["extmetadata"]["License"]["value"]
                if license in ["cc0", "pd"]:
                    license = "cc-0"
            except KeyError:
                license = img["extmetadata"]["LicenseShortName"]["value"]
            info = {
                "id": item.get("pageid", None),
                "name": item["title"].split(":", 1)[-1],
                "author": img["user"],
                "license": license,
                "summary": "",  # No data
                "thumbnail": img["thumburl"],
                "created": item["touched"],
                "descriptionurl": item["canonicalurl"],
                "popularity": 0,  # No data
                "file": img["url"],
            }

            file = WikiMediaFile(self.remote_source, info)
            yield file


class WikiMediaSource(RemoteSource):
    name = 'Wikimedia'
    desc = 'Wikimedia is a global movement whose mission is to bring ' \
           'free educational content to the world.'
    icon = "icons/wikicommons.svg"
    source_type = SourceType.ILLUSTRATION
    file_cls = WikiMediaFile
    page_cls = WikiMediaPage
    is_default = False
    is_enabled = True
    options_window_width = 300
    items_per_page = 16
    window_cls = WikiMediaWindow
    base_url = "https://commons.wikimedia.org/w/api.php"

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
            page = WikiMediaPage(self, page_no, results)
            self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query):
        self.results = []
        self.query = sanitize_query(query)
        self.window.clear_pages()
        self.window.show_spinner()

        params = {
            "action": "query",
            "format": "json",
            "uselang": "en",
            "generator": "search",
            "gsrsearch": "filetype:bitmap|drawing filemime:svg " + query,
            "gsrlimit": 40,
            "gsroffset": 0,
            "gsrinfo": "totalhits|suggestion",
            "gsrprop": "size|wordcount",
            "gsrnamespace": 6,
            "prop": "info|imageinfo|entityterms",
            "inprop": "url",
            "iiprop": "url|size|mime|user|extmetadata",
            "iiurlheight": 180,
            "wbetterms": "label",
        }
        pages = []
        try:
            response = self.session.get(self.base_url, params=params).json()
            if "error" in response:
                raise IOError(response["error"]["info"])
            pages = response["query"]["pages"].values()
        except:
            pass
        self.results.extend(pages)
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
        lic = LICENSES.get(info["license"])
        text = f'<span  size="large" weight="normal" >Illustration by</span>\n\n' + \
               f'<span  size="large" weight="bold" >{info["author"]}</span>\n\n' + \
               f'<span  size="large" weight="normal" >{info["name"]}</span>\n\n' + \
               f'<span  size="medium" weight="normal" >Available under the {lic["name"]} license, ' if lic else '' \
               f'<a href="{lic["url"]}">More Info</a></span>' if lic else ''
        text.replace("&", "&amp;")
        self.options_window.options["info"].view.set_markup(text)
