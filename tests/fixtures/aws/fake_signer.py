def fake_request_creator():
    return FakeRequest()

class FakeRequest(object):
    headers = None

class FakeSigner(object):
    def __init__(self, request=None) -> None:
        self.request = request if request else FakeRequest()

    def add_auth(self, request) -> None:
        """
        A fake for getting a request object that
        :return:
        """
        request.headers = {"FakeAuthorization": "a", "FakeTime": "today"}

    def get_headers(self):
        self.add_auth(self.request)
        return self.request.headers