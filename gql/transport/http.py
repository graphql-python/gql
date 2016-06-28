class HTTPTransport(object):
    def __init__(self, url, client_headers=None):
        self.url = url
        self.client_headers = None
