import pytest


class FakeCredentials(object):
    def __init__(
        self, access_key=None, secret_key=None, method=None, token=None, region=None
    ):
        self.region = region if region else "us-east-1a"
        self.access_key = access_key if access_key else "fake-access-key"
        self.secret_key = secret_key if secret_key else "fake-secret-key"
        self.method = method if method else "shared-credentials-file"
        self.token = token if token else "fake-token"


@pytest.fixture
def fake_credentials_factory():
    def _fake_credentials_factory(
        access_key=None, secret_key=None, method=None, token=None, region=None
    ):
        return FakeCredentials(
            access_key=access_key,
            secret_key=secret_key,
            method=method,
            token=token,
            region=region,
        )

    yield _fake_credentials_factory
