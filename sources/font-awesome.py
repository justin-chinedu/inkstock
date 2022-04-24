
from ntpath import join
from remote import RemoteSource, RemoteFile, RemotePage
from genericpath import exists
import json
import sys
sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')


class FAIcon(RemoteFile):
    thumbnail = property(lambda self: self.remote.to_local_file(
        self.info["thumbnail"], self.info["name"] + '.svg'))

    def get_file(self): return self.remote.to_local_file(
        self.info["file"], self.info["name"] + '.svg')


class FAPage(RemotePage):
    def __init__(self, remote_source: RemoteSource, page_no, results):
        super().__init__(remote_source, page_no)
        self.results = results
        self.remote_source = remote_source

    def get_page_content(self):
        for key, value in self.results:
            name =  "-".join(key.split("-")[:-1])
            category = key.split("-")[-1]
            url = f"https://raw.githubusercontent.com/FortAwesome/Font-Awesome/6.x/svgs/{category}/{name}.svg"
            info = {
                "id": name,
                "name": name,
                "author": url.split('/')[3],
                "thumbnail": url,
                "license": """The Font Awesome Free download is licensed under a Creative Commons
                    Attribution 4.0 International License and applies to all icons packaged
                    as SVG and JS file types.
                    """,
                "summary": "",
                "file": url,
            }

            yield FAIcon(self.remote_source, info)


class FASource(RemoteSource):
    name = 'Font Awesome Icons'
    desc = "Font Awesome is the Internet's icon library and toolkit, used by millions of designers, developers, and content creators."
    icon = "icons/font-awesome.png"
    file_cls = FAIcon
    page_cls = FAPage
    is_default = False
    is_enabled = True
    is_optimized = False
    items_per_page = 10

    def __init__(self, cache_dir):
        super().__init__(cache_dir)
        json = 'json/font-awesome.json'
        json_exists = exists(json)
        opt_json = 'json/font-awesome-optimized.json'
        optimized_json_exists = exists(opt_json)
        if optimized_json_exists:
            self.opt_icon_map = read_map_file(
                opt_json)
            self.is_optimized = True
        elif json_exists:
            self.icon_map = read_map_file(json)
        else:
            raise FileNotFoundError(
                "Cannot find any font awesome json files in json folder")

    def get_page(self, page_no: int):
        self.current_page = page_no
        results = self.results[page_no *
                               self.items_per_page: self.items_per_page*(page_no + 1)]
        if not results:
            return None
        return FAPage(self, page_no, results)

    def search(self, query):
        query = query.lower().replace(' ', '_')
        self.results = [(key, value) for key, value in self.icon_map.items()
                        if key.startswith(query)]
        return self.get_page(0)


def read_map_file(path):
    with open(path, mode='r') as f:
        m = json.load(f)
        f.close()
    return m
