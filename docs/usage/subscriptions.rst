Subscriptions
=============

Using the :ref:`websockets transport <websockets_transport>`, it is possible to execute GraphQL subscriptions,
either using the sync or async usage.

The async usage is recommended for any non-trivial tasks (it allows efficient concurrent queries and subscriptions).

See :ref:`Async permanent session <async_permanent_session>`  and :ref:`Async advanced usage <async_advanced_usage>`
for more advanced examples.

.. note::

    The websockets transport can also execute queries or mutations, it is not restricted to subscriptions.

Sync
----

.. code-block:: python

    from gql import Client, gql
    from gql.transport.websockets import WebsocketsTransport

    # Select your transport with a defined url endpoint
    transport = WebsocketsTransport(url='wss://your_server/graphql')

    # Create a GraphQL client using the defined transport
    client = Client(transport=transport)

    # Provide a GraphQL subscription query
    query = gql('''
        subscription yourSubscription {
            ...
        }
    ''')

    # Connect and subscribe to the results using a simple 'for'
    for result in client.subscribe(query):
        print (result)

Async
-----

.. code-block:: python

    import asyncio

    from gql import Client, gql
    from gql.transport.websockets import WebsocketsTransport


    async def main():

        # Select your transport with a defined url endpoint
        transport = WebsocketsTransport(url='wss://your_server/graphql')

        # Create a GraphQL client using the defined transport
        client = Client(transport=transport)

        # Provide a GraphQL subscription query
        query = gql('''
            subscription yourSubscription {
                ...
            }
        ''')

        # Using `async with` on the client will start a connection on the transport
        # and provide a `session` variable to execute queries on this connection
        async with client as session:

            # Then get the results using 'async for'
            async for result in client.subscribe(query):
                print (result)


    asyncio.run(main())
