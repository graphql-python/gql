import pytest


class FakeSession(object):
    def __init__(self, credentials, region_name):
        self._credentials = credentials
        self._region_name = region_name

    def get_credentials(self):
        return self._credentials

    def _resolve_region_name(self):
        return self._region_name


@pytest.fixture
def fake_session_factory(fake_credentials_factory):
    def _fake_session_factory():
        return FakeSession(credentials=fake_credentials_factory, region='fake-region')

    yield _fake_session_factory
