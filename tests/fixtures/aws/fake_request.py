import pytest


class FakeRequest(object):
    headers = None

    def __init__(self, request_props=None):
        if not isinstance(request_props, dict):
            return
        self.method = request_props.get("method")
        self.url = request_props.get("url")
        self.headers = request_props.get("headers")
        self.context = request_props.get("context")
        self.body = request_props.get("body")


@pytest.fixture
def fake_request_factory():
    def _fake_request_factory(request_props=None):
        return FakeRequest(request_props=request_props)

    yield _fake_request_factory
