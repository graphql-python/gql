import pytest

@pytest.fixture
def fake_credentials_factory():
    def _fake_credentials_factory(access_key=None, secret_key=None, method=None, token=None):
        return {
            "access_key": access_key if access_key else "fake-access-key",
            "secret_key": secret_key if secret_key else "fake-secret-key",
            "method": method if method else "shared-credentials-file",
            "token": token if token else "fake-token",
        }
    yield _fake_credentials_factory