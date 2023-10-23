Introduction
============

`GQL 3`_ is a `GraphQL`_ Client for Python 3.7+ which plays nicely with other
graphql implementations compatible with the spec.

Under the hood, it uses `GraphQL-core`_ which is a Python port of `GraphQL.js`_,
the JavaScript reference implementation for GraphQL.

Installation
------------

You can install GQL 3 and all the extra dependencies using pip_::

    pip install "gql[all]"

To have the latest pre-releases versions of gql, you can use::

    pip install --pre "gql[all]"

After installation, you can start using GQL by importing from the top-level
:mod:`gql` package.

Less dependencies
^^^^^^^^^^^^^^^^^

GQL supports multiple :ref:`transports <transports>` to communicate with the backend.
Each transport can necessitate specific dependencies.
If you only need one transport you might want to install only the dependency needed for your transport,
instead of using the "`all`" extra dependency as described above, which installs everything.

If for example you only need the :ref:`AIOHTTPTransport <aiohttp_transport>`,
which needs the :code:`aiohttp` dependency, then you can install GQL with::

    pip install gql[aiohttp]

The corresponding between extra dependencies required and the GQL classes is:

+---------------------+----------------------------------------------------------------+
| Extra dependencies  | Classes                                                        |
+=====================+================================================================+
| aiohttp             | :ref:`AIOHTTPTransport <aiohttp_transport>`                    |
+---------------------+----------------------------------------------------------------+
| websockets          | :ref:`WebsocketsTransport <websockets_transport>`              |
|                     |                                                                |
|                     | :ref:`PhoenixChannelWebsocketsTransport <phoenix_transport>`   |
|                     |                                                                |
|                     | :ref:`AppSyncWebsocketsTransport <appsync_transport>`          |
+---------------------+----------------------------------------------------------------+
| requests            | :ref:`RequestsHTTPTransport <requests_transport>`              |
+---------------------+----------------------------------------------------------------+
| httpx               | :ref:`HTTPTXTransport <httpx_transport>`                       |
|                     |                                                                |
|                     | :ref:`HTTPXAsyncTransport <httpx_async_transport>`             |
+---------------------+----------------------------------------------------------------+
| botocore            | :ref:`AppSyncIAMAuthentication <appsync_iam_auth>`             |
+---------------------+----------------------------------------------------------------+

.. note::

    It is also possible to install multiple extra dependencies if needed
    using commas: :code:`gql[aiohttp,websockets]`

Installation with conda
^^^^^^^^^^^^^^^^^^^^^^^

It is also possible to install gql using `conda`_.

To install gql with all extra dependencies::

    conda install gql-with-all

To install gql with less dependencies, you might want to instead install a combinaison of the
following packages: :code:`gql-with-aiohttp`, :code:`gql-with-websockets`, :code:`gql-with-requests`,
:code:`gql-with-botocore`

If you want to have the latest pre-releases version of gql and graphql-core, you can install
them with conda using::

    conda install -c conda-forge -c conda-forge/label/graphql_core_alpha -c conda-forge/label/gql_beta gql-with-all

Reporting Issues and Contributing
---------------------------------

Please visit the `GitHub repository for gql`_ if you're interested in the current development or
want to report issues or send pull requests.

We welcome all kinds of contributions if the coding guidelines are respected.
Please check the  `Contributing`_ file to learn how to make a good pull request.

.. _GraphQL: https://graphql.org/
.. _GraphQL-core: https://github.com/graphql-python/graphql-core
.. _GraphQL.js: https://github.com/graphql/graphql-js
.. _GQL 3: https://github.com/graphql-python/gql
.. _pip: https://pip.pypa.io/
.. _GitHub repository for gql: https://github.com/graphql-python/gql
.. _Contributing: https://github.com/graphql-python/gql/blob/master/CONTRIBUTING.md
.. _conda: https://docs.conda.io
