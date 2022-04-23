
import json
import sys

sys.path.insert(
    1, '/home/justin/inkscape-dev/inkscape/inkscape-data/inkscape/extensions/other/inkstock')

from remote import RemoteFile, RemotePage, RemoteSource

class UndrawIllustration(RemoteFile):
    thumbnail = property(lambda self: self.remote.to_local_file(self.info["thumbnail"], self.info["name"] + '.svg'))
    get_file = lambda self: self.remote.to_local_file(self.info["file"], self.info["name"] + '.svg')


class UndrawPage(RemotePage):
    def __init__( self,remote_source : RemoteSource ,page_no, results):
        super().__init__( remote_source ,page_no)
        self.results =  results
        self.remote_source = remote_source
        
    def get_page_content(self):
        for result in  self.results:
            yield UndrawIllustration(self.remote_source, result)
        

class Undraw(RemoteSource):
    name = "Undraw"
    desc = "Open-source illustrations for any idea you can imagine and create."
    icon = "icons/undraw.png"
    file_cls = UndrawIllustration
    page_cls = UndrawPage
    is_default = False
    is_enabled = True
    items_per_page = 10
    reqUrl = "https://undraw.co/api/search"


    def get_page(self, page_no: int):
        self.current_page = page_no
        results = self.results[page_no * self.items_per_page: self.items_per_page*(page_no + 1)]
        if not results : return None
        return UndrawPage(self, page_no, results)
    
    def search(self, query, tags=...):
        self.results = []
        query = query.lower().replace(' ', '_')

        headersList = {
        "Accept": "*/*",
        "User-Agent": "Inkscape",
        "Content-Type": "application/json" 
        }

        payload = json.dumps({"query": query})

        response = self.session.request("POST", self.reqUrl, data=payload,  headers=headersList)
        illus = response.json()["illos"]
        for item in illus:
            result = {
                "thumbnail" : item["image"],
                "file" : item["image"],
                "name" : item["title"],
                "license" : ""
            }
            self.results.append(result)
        
        return self.get_page(0)

    
