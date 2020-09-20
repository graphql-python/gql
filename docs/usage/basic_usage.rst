.. _basic_usage:

Basic usage
-----------

In order to execute a GraphQL request against a GraphQL API:

* create your gql :ref:`transport <transports>` in order to choose the destination url
  and the protocol used to communicate with it
* create a gql :class:`Client <gql.client.Client>` with the selected transport
* parse a query using :func:`gql <gql.gql>`
* execute the query on the client to get the result

.. literalinclude:: ../code_examples/aiohttp_sync.py

.. warning::

    Please note that this basic example won't work if you have an asyncio event loop running. In some
    python environments (as with Jupyter which uses IPython) an asyncio event loop is created for you.
    In that case you should use instead the :ref:`Async Usage example<async_usage>`.

