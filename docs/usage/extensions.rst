.. _extensions:

Extensions
----------

Request extensions
^^^^^^^^^^^^^^^^^^

The `GraphQL over HTTP spec <https://github.com/graphql/graphql-over-http>`_
defines an optional :code:`extensions` field on requests. This is sent as a
top-level key in the request payload alongside :code:`query`, :code:`variables`,
and :code:`operationName`.

You can use this to pass protocol extensions such as
`trusted documents <https://graphql.org/learn/security/#trusted-documents>`_:

.. code-block:: python

    from gql import Client, GraphQLRequest
    from gql.transport.aiohttp import AIOHTTPTransport

    transport = AIOHTTPTransport(url="https://example.com/graphql")

    async with Client(transport=transport) as session:

        request = GraphQLRequest(
            "query { viewer { name } }",
            extensions={
                "document-id": "foo",
            },
        )

        result = await session.execute(request)

Response extensions
^^^^^^^^^^^^^^^^^^^

When you execute (or subscribe) GraphQL requests, the server will send
responses which may have 3 fields:

- data: the serialized response from the backend
- errors: a list of potential errors
- extensions: an optional field for additional data

If there are errors in the response, then the
:code:`execute` or :code:`subscribe` methods will
raise a :code:`TransportQueryError`.

If no errors are present, then only the data from the response is returned by default.

.. code-block:: python

    result = client.execute(query)
    # result is here the content of the data field

If you need to receive the extensions data too, then you can run the
:code:`execute` or :code:`subscribe` methods with :code:`get_execution_result=True`.

In that case, the full execution result is returned and you can have access
to the extensions field

.. code-block:: python

    result = client.execute(query, get_execution_result=True)
    # result is here an ExecutionResult instance

    # result.data is the content of the data field
    # result.extensions is the content of the extensions field
