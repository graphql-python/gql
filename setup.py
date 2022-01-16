import os

from setuptools import setup, find_packages

install_requires = [
    "graphql-core>=3.2,<3.3",
    "yarl>=1.6,<2.0",
]

scripts = [
    "scripts/gql-cli",
]

tests_requires = [
    "parse==1.15.0",
    "pytest==6.2.5",
    "pytest-asyncio==0.16.0",
    "pytest-cov==3.0.0",
    "mock==4.0.2",
    "vcrpy==4.0.2",
    "aiofiles",
]

dev_requires = [
    "black==19.10b0",
    "check-manifest>=0.42,<1",
    "flake8==3.8.1",
    "isort==4.3.21",
    "mypy==0.910",
    "sphinx>=3.0.0,<4",
    "sphinx_rtd_theme>=0.4,<1",
    "sphinx-argparse==0.2.5",
    "types-aiofiles",
    "types-mock",
    "types-requests",
] + tests_requires

install_aiohttp_requires = [
    "aiohttp>=3.7.1,<3.9.0",
]

install_requests_requires = [
    "requests>=2.26,<3",
    "requests_toolbelt>=0.9.1,<1",
    "urllib3>=1.26",
]

install_websockets_requires = [
    "websockets>=9,<10;python_version<='3.6'",
    "websockets>=10,<11;python_version>'3.6'",
]

install_botocore_requires = [
    "botocore>=1.21,<2",
]

install_all_requires = (
    install_aiohttp_requires + install_requests_requires + install_websockets_requires + install_botocore_requires
)

# Get version from __version__.py file
current_folder = os.path.abspath(os.path.dirname(__file__))
about = {}
with open(os.path.join(current_folder, "gql", "__version__.py"), "r") as f:
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
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    keywords="api graphql protocol rest relay gql client",
    packages=find_packages(include=["gql*"]),
    # PEP-561: https://www.python.org/dev/peps/pep-0561/
    package_data={"gql": ["py.typed"]},
    install_requires=install_requires,
    tests_require=install_all_requires + tests_requires,
    extras_require={
        "all": install_all_requires,
        "test": install_all_requires + tests_requires,
        "test_no_transport": tests_requires,
        "dev": install_all_requires + dev_requires,
        "aiohttp": install_aiohttp_requires,
        "requests": install_requests_requires,
        "websockets": install_websockets_requires,
        "botocore": install_botocore_requires,
    },
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    scripts=scripts,
)
