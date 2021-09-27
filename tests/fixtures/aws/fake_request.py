import pytest


class FakeRequest(object):
    headers = None


@pytest.fixture
def fake_request_factory():
    def _fake_request_factory():
        return FakeRequest()
    yield _fake_request_factory
