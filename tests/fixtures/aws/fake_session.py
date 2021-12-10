import pytest


class FakeSession(object):
    def __init__(self, credentials, region_name):
        self._credentials = credentials
        self._region_name = region_name

    def get_default_client_config(self):
        return

    def get_credentials(self):
        return self._credentials

    def _resolve_region_name(self, region_name, client_config):
        return region_name if region_name else self._region_name


@pytest.fixture
def fake_session_factory(fake_credentials_factory):
    def _fake_session_factory(credentials=fake_credentials_factory()):
        return FakeSession(credentials=credentials, region_name="fake-region")

    yield _fake_session_factory
