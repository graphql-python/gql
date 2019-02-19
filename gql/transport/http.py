class HTTPTransport(object):

    def __init__(self, url, headers=None, cookies=None, **kwargs):
        self.url = url
        self.headers = headers
        self.cookies = cookies
        self.kwargs = kwargs
