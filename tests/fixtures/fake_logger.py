import pytest


class FakeLogger(object):
    def __init__(self, messages=None):
        self._messages = messages if messages else []

    def log(self, level, message):
        self._messages.append("LEVEL {}: {}".format(level, message))


@pytest.fixture
def fake_logger_factory():
    def _fake_logger_factory(messages=None):
        return FakeLogger(messages=messages)

    yield _fake_logger_factory
