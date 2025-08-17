import os

from setuptools import setup, find_packages

install_requires = [
    "graphql-core>=3.2,<3.3",
    "yarl>=1.6,<2.0",
    "backoff>=1.11.1,<3.0",
    "anyio>=3.0,<5",
]

console_scripts = [
    "gql-cli=gql.cli:gql_cli",
]

tests_requires = [
    "parse==1.20.2",
    "pytest==8.3.4",
    "pytest-asyncio==0.25.3",
    "pytest-console-scripts==1.4.1",
    "pytest-cov==6.0.0",
    "vcrpy==7.0.0",
    "aiofiles",
]

dev_requires = [
    "black==25.1.0",
    "check-manifest>=0.42,<1",
    "flake8==7.1.2",
    "isort==6.0.1",
    "mypy==1.15",
    "sphinx>=7.0.0,<8;python_version<='3.9'",
    "sphinx>=8.1.0,<9;python_version>'3.9'",
    "sphinx_rtd_theme>=3.0.2,<4",
    "sphinx-argparse==0.5.2",
    "types-aiofiles",
    "types-requests",
] + tests_requires

install_aiohttp_requires = [
    "aiohttp>=3.11.2,<4",
]

install_requests_requires = [
    "requests>=2.26,<3",
    "requests_toolbelt>=1.0.0,<2",
]

install_httpx_requires = [
    "httpx>=0.27.0,<1",
]

install_websockets_requires = [
    "websockets>=14.2,<16",
]

install_botocore_requires = [
    "botocore>=1.21,<2",
]

install_aiofiles_requires = [
    "aiofiles",
]

install_all_requires = (
    install_aiohttp_requires + install_requests_requires + install_httpx_requires + install_websockets_requires + install_botocore_requires + install_aiofiles_requires
)

# Get version from __version__.py file
current_folder = os.path.abspath(os.path.dirname(__file__))
about = {}
with open(os.path.join(current_folder, "gql", "__version__.py")) as f:
    exec(f.read(), about)

setup(
    name="gql",
    version=about["__version__"],
    description="GraphQL client for Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/graphql-python/gql",
    author="Syrus Akbary",
    author_email="me@syrusakbary.com",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    keywords="api graphql protocol rest relay gql client",
    packages=find_packages(include=["gql*"]),
    # PEP-561: https://www.python.org/dev/peps/pep-0561/
    package_data={"gql": ["py.typed"]},
    install_requires=install_requires,
    extras_require={
        "all": install_all_requires,
        "test": install_all_requires + tests_requires,
        "test_no_transport": tests_requires,
        "dev": install_all_requires + dev_requires,
        "aiohttp": install_aiohttp_requires,
        "requests": install_requests_requires,
        "httpx": install_httpx_requires,
        "websockets": install_websockets_requires,
        "botocore": install_botocore_requires,
        "aiofiles": install_aiofiles_requires,
    },
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    entry_points={"console_scripts": console_scripts},
)
