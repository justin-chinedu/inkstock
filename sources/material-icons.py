import sys
sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from remote import RemoteFile, RemotePage, RemoteSource
import json
import os
import time
from os.path import exists
from numpy import sort
import requests

class MaterialIcon(RemoteFile):
    thumbnail = property(lambda self: self.remote.to_local_file(self.info["thumbnail"], self.info["name"] + '.svg'))
    get_file = lambda self: self.remote.to_local_file(self.info["file"], self.info["name"] + '.svg')

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

            yield MaterialIcon(self.remote_source, info)


class MaterialIconsSource(RemoteSource):
    name = 'Material Icons'
    desc = "Material design icons is the official icon set from Google. They can be browsed at https://fonts.google.com/icons. The icons are designed under the material design guidelines."
    icon = "icons/material-icons.png"
    file_cls = MaterialIcon
    page_cls = MaterialIconsPage
    is_default = True
    is_enabled = True
    is_optimized = False
    items_per_page = 10

    def __init__(self, cache_dir):
        super().__init__(cache_dir)
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
        results = self.results[page_no * self.items_per_page: self.items_per_page*(page_no + 1)]
        if not results : return None
        return MaterialIconsPage(self, page_no, results)

    def search(self, query):
        query = query.lower().replace(' ', '_')
        if self.is_optimized:
            try:
                self.results = self.opt_icon_map[query]
            except:
                self.results = []
        else:
            self.results = [value for key, value in self.icon_map.items()
                            if key.startswith(query)]
        return self.get_page(0)


    def result_to_cls(self, info):
        if callable(info):
            return self.page_cls(self, info, self.current_page+1)
        return self.file_cls(self, info)


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

 