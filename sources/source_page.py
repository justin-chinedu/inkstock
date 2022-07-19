class RemotePage:

    def __init__(self, remote_source, page_no: int):
        self.page_no = page_no
        self.remote_source = remote_source

    def get_page_content(self):
        """Should be implemented
            Simply yields a list of remotefiles
        """
        raise NotImplementedError(
            "You must implement a get_page_content function for this remote page!"
        )


class NoResultsPage:
    def __init__(self, query: str):
        self.message = f'<span  size="large" weight="normal" >No search results for</span>\n' + \
                       f'<span  size="large" weight="bold" >{query}</span>\n'

