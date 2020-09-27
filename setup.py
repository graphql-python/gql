import os

from setuptools import setup, find_packages

install_requires = [
    "aiohttp==3.6.2",
    "graphql-core>=3.1,<3.2",
    "requests>=2.23,<3",
    "websockets>=8.1,<9",
    "yarl>=1.4,<2.0",
]

scripts = [
    "scripts/gql-cli",
]

tests_require = [
    "parse==1.15.0",
    "pytest==5.4.2",
    "pytest-asyncio==0.11.0",
    "pytest-cov==2.8.1",
    "mock==4.0.2",
    "vcrpy==4.0.2",
]

dev_requires = [
    "black==19.10b0",
    "check-manifest>=0.42,<1",
    "flake8==3.8.1",
    "isort==4.3.21",
    "mypy==0.770",
    "sphinx>=3.0.0,<4",
    "sphinx_rtd_theme>=0.4,<1",
] + tests_require

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
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: PyPy",
    ],
    keywords="api graphql protocol rest relay gql client",
    packages=find_packages(include=["gql*"]),
    install_requires=install_requires,
    tests_require=tests_require,
    extras_require={"test": tests_require, "dev": dev_requires},
    include_package_data=True,
    zip_safe=False,
    platforms="any",
    scripts=scripts,
)
