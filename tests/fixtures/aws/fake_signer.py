import pytest


@pytest.fixture
def fake_signer_factory(fake_request_factory):
    def _fake_signer_factory(request=None):
        if not request:
            request = fake_request_factory()
        return FakeSigner(request=request)

    yield _fake_signer_factory


class FakeSigner(object):
    def __init__(self, request=None) -> None:
        self.request = request

    def add_auth(self, request) -> None:
        """
        A fake for getting a request object that
        :return:
        """
        request.headers = {"FakeAuthorization": "a", "FakeTime": "today"}

    def get_headers(self):
        self.add_auth(self.request)
        return self.request.headers
