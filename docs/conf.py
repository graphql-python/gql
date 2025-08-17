# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('./..'))


# -- Project information -----------------------------------------------------

project = 'gql'
copyright = '2025, graphql-python.org'
author = 'graphql-python.org'

# The full version, including alpha/beta/rc tags
from gql import __version__
release = __version__


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinxarg.ext',
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx_rtd_theme'
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

# Output file base name for HTML help builder.
htmlhelp_basename = 'gql-3-doc'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# -- AutoDoc configuration -------------------------------------------------
# autoclass_content = "both"
autodoc_default_options = {
    'members': True,
    'inherited-members': True,
    'special-members': '__init__',
    'undoc-members': True,
    'show-inheritance': True
}
autosummary_generate = True

# -- Intersphinx configuration ---------------------------------------------
intersphinx_mapping = {
    'aiohttp': ('https://docs.aiohttp.org/en/stable/', None),
    'graphql': ('https://graphql-core-3.readthedocs.io/en/latest/', None),
    'multidict': ('https://multidict.aio-libs.org/en/stable/', None),
    'python': ('https://docs.python.org/3/', None),
    'requests': ('https://requests.readthedocs.io/en/latest/', None),
    'websockets': ('https://websockets.readthedocs.io/en/11.0.3/', None),
    'yarl': ('https://yarl.aio-libs.org/en/stable/', None),
}

nitpick_ignore = [
    # graphql-core: should be fixed
    ('py:class', 'graphql.execution.execute.ExecutionResult'),
    ('py:class', 'Source'),
    ('py:class', 'GraphQLSchema'),

    # asyncio: should be fixed
    ('py:class', 'asyncio.locks.Event'),

    # aiohttp: should be fixed
    # See issue: https://github.com/aio-libs/aiohttp/issues/10468
    ('py:class', 'aiohttp.client.ClientSession'),
    ('py:class', 'aiohttp.client_reqrep.Fingerprint'),
    ('py:class', 'aiohttp.helpers.BasicAuth'),

    # multidict: should be fixed
    ('py:class', 'multidict._multidict.CIMultiDictProxy'),
    ('py:class', 'multidict._multidict.CIMultiDict'),
    ('py:class', 'multidict._multidict.istr'),

    # websockets: first bump websockets version
    ('py:class', 'websockets.datastructures.SupportsKeysAndGetItem'),
    ('py:class', 'websockets.typing.Subprotocol'),

    # httpx: no sphinx docs yet https://github.com/encode/httpx/discussions/3091
    ('py:class', 'httpx.AsyncClient'),
    ('py:class', 'httpx.Client'),
    ('py:class', 'httpx.Headers'),

    # botocore: no sphinx docs
    ('py:class', 'botocore.auth.BaseSigner'),
    ('py:class', 'botocore.awsrequest.AWSRequest'),
    ('py:class', 'botocore.credentials.Credentials'),
    ('py:class', 'botocore.session.Session'),

    # gql: ignore private classes
    ('py:class', 'gql.transport.httpx._HTTPXTransport'),
    ('py:class', 'gql.client._CallableT'),
]
