import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-online",
        action="store_true",
        default=False,
        help="run tests necessitating online ressources",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "online: mark test as necessitating external online ressources"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-online"):
        # --run-online given in cli: do not skip online tests
        return
    skip_online = pytest.mark.skip(reason="need --run-online option to run")
    for item in items:
        if "online" in item.keywords:
            item.add_marker(skip_online)
