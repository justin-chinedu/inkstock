import math
import os

import requests

from inkex.gui import asyncme


class DownloadManager:

    def __init__(self, window):
        self.window = window
        self.files = {}
        self.session = requests.session()
        headers = {
            "user-agent": "InkStock"
        }
        self.session.headers.update(headers)

    def add_files(self, source, files):
        self.files[source] = files
        l = 0
        for item in self.files.values():
            l += len(item)
        self.window.no_of_selected.set_text(f"{l} items selected")
        if l > 0:
            self.window.import_files_btn.set_sensitive(True)
        else:
            self.window.import_files_btn.set_sensitive(False)

    def download(self, url, filename):
        name = os.path.basename(filename)
        bytes_downloaded = 0
        out = open(filename, mode="wb+")
        with self.session.get(url, stream=True) as r:
            total = r.headers["content-length"]
            total = int(total)
            for data in r.iter_content(chunk_size=5000):
                bytes_downloaded += len(data)
                out.write(data)
                self.show_progress(bytes_downloaded, total, name)
            out.close()

    @asyncme.mainloop_only
    def show_progress(self, bytes_downloaded, total, name):
        if total:
            percent = bytes_downloaded / total
            self.window.progress.set_text(f"Fetching {name}...")
            self.window.progress.set_show_text()
            self.window.progress.set_fraction(percent)
        else:
            self.window.progress.set_text(f"Fetching {name}...")
            self.window.progress.set_show_text()
            self.window.progress.pulse()
