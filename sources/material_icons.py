import sys
from time import sleep

from numpy import sort

from inkex.gui import asyncme
from utils.constants import CACHE_DIR
from utils.pixelmap import PixmapManager, SIZE_ASPECT_GROW, SIZE_ASPECT_CROP
from windows.basic_window import BasicWindow
from windows.options_window import OptionsWindow, OptionType

sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from remote import RemoteFile, RemotePage, RemoteSource
import json
from os.path import exists


class MaterialWindow(BasicWindow):
    name = "material_window"

    def __init__(self, gapp):
        self.name = "basic_window"
        super().__init__(gapp)

    def get_pixmaps(self):
        pix = PixmapManager(CACHE_DIR, scale=8,
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


class MaterialIcon(RemoteFile):
    def __init__(self, remote, info):
        super().__init__(remote, info)
        self.name = f"{self.info['name']}-material"

    def get_thumbnail(self):
        name = self.name + ".svg"
        return self.remote.to_local_file(self.info["thumbnail"], name)

    def get_file(self):
        name = self.name + "file.svg"
        return self.remote.to_local_file(self.info["file"], name)

class MaterialIconsPage(RemotePage):
    def __init__( self,remote_source : RemoteSource ,page_no, results):
        super().__init__( remote_source ,page_no)
        self.results =  results
        self.remote_source = remote_source

    def get_page_content(self):
        for url in  self.results:
        
            if url.split('/')[9].replace('materialicons', '') == '':
                icon_type = ''
            else:
                icon_type = '-' + \
                    url.split('/')[9].replace('materialicons', '')

            name = url.split('/')[8] + '-' + \
                url.split('/')[7] + icon_type

            info =  {
                "id": name,
                "name": name,
                "author": url.split('/')[3],
                "thumbnail": url,
                "license": """Apache License 2.0
                Permissions:
                    Commercial use
                    Modification
                    Distribution
                    Patent use
                    Private use
                """,
                "summary": "",
                "file": url,
            }

            icon = MaterialIcon(self.remote_source, info)
            yield icon


class MaterialIconsSource(RemoteSource):
    name = 'Material Icons'
    desc = "Material design icons is the official icon set from Google. They can be browsed at <a href='https://fonts.google.com/icons'>Material Icons</a>. The icons are designed under the material design guidelines."
    icon = "icons/material-icons.png"
    file_cls = MaterialIcon
    page_cls = MaterialIconsPage
    is_default = True
    is_enabled = True
    is_optimized = False
    options_window_width = 350
    items_per_page = 16
    window_cls = MaterialWindow

    def __init__(self, cache_dir, dm):
        super().__init__(cache_dir, dm)
        self.query = ""
        self.results = []
        self.options = {}
        self.options_window = OptionsWindow(self)
        self.options_window.set_option("query", None, OptionType.SEARCH, "Search Material Icons")
        self.options_window.set_option(
            "color", None, OptionType.COLOR, "Choose icon color")

        # -----------------------
        json_exists = exists('json/material-icons.json')
        optimized_json_exists = exists('json/material-icons-optimized.json')
        if optimized_json_exists:
            self.opt_icon_map = read_map_file(
                'json/material-icons-optimized.json')
            self.is_optimized = True
        elif json_exists:
            self.icon_map = read_map_file('json/material-icons.json')
        else:
            raise FileNotFoundError("Cannot find any material_icon json files in json folder")

    def get_page(self, page_no: int):
        self.current_page = page_no
        self.window.show_spinner()
        results = self.results[page_no * self.items_per_page: self.items_per_page * (page_no + 1)]
        if results:
            page = MaterialIconsPage(self, page_no, results)
            self.window.add_page(page)

    @asyncme.run_or_none
    def search(self, query, tags=None):
        self.results = []
        query = query.lower().replace(' ', '_')
        self.query = query
        self.window.clear_pages()
        self.window.show_spinner()
        if self.is_optimized:
            try:
                self.results = self.opt_icon_map[query]
            except:
                self.results = []
        else:
            self.results = [value for key, value in self.icon_map.items()
                            if key.startswith(query)]
        self.get_page(0)

    def on_window_attached(self, window: BasicWindow, window_pane):
        super().on_window_attached(window, window_pane)
        self.query = "a"
        asyncme.run_or_none(self.search)("a")

    def on_change(self, options):
        self.query = options["query"]
        self.options = options
        if self.window and self.query:
            self.search(self.query)


def get_results(results):
    for index, result in enumerate(results):
        if index == 10:
            yield get_results
            break

        if result.split('/')[9].replace('materialicons', '') == '':
            icon_type = ''
        else:
            icon_type = '-' + \
                result.split('/')[9].replace('materialicons', '')

        name = result.split('/')[8] + '-' + \
            result.split('/')[7] + icon_type

        yield {
            "id": name,
            "name": name,
            "author": result.split('/')[3],
            "thumbnail": result,
            "license": """
            Apache License 2.0
            Permissions:
                Commercial use
                Modification
                Distribution
                Patent use
                Private use
            """,
            "summary": "",
            "file": result,
        }


def all_suffixes(s):
    suffixes = [s[:-i] for i in range(1, len(s))]
    suffixes.insert(0, s)
    suffixes_reversed = [s[i:] for i in range(1, len(s))]
    return list(sort(list({*suffixes, *suffixes_reversed})))

 
def optimize(icon_map):
    optimised_map = {}
    for word in icon_map.keys():
        suffixes = all_suffixes(word)
        for suffix in suffixes:
            if not (suffix in optimised_map.keys()):
                optimised_map[suffix] = []
            optimised_map[suffix].append(icon_map[word])
    sorted_optimized_map = {}
    for (key, value) in optimised_map.items():
        def get_index(s, substr: str):
            try:
                index = s.index(substr)
                if s.startswith('d'):
                    pass
                return index
            except:
                return len(value)

        names = list(map(lambda x: x.split('/')[8], value))
        sorted_names = sorted(names, key=lambda x: get_index(x, key))

        def get_value_index(s):
            try:
                name = s.split('/')[8]
                index = sorted_names.index(name)
                return index
            except:
                return -1
        new_value = sorted(value, key=lambda x: get_value_index(x))
        sorted_optimized_map[key] = new_value
    return sorted_optimized_map


def read_map_file(path):
    with open(path, mode='r') as f:
        m = json.load(f)
        f.close()
    return m

def save_json_file(json_file):
    with open('/sdcard/material-icons-optimized.json', mode='wt') as f:
        f.write(json.dumps(json_file))
        f.flush()

 