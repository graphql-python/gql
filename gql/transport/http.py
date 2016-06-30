class HTTPTransport(object):

    def __init__(self, url, headers=None):
        self.url = url
        self.headers = headers
