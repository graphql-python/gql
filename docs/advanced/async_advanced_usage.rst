.. _async_advanced_usage:

Async advanced usage
====================

It is possible to send multiple GraphQL queries (query, mutation or subscription) in parallel,
on the same websocket connection, using asyncio tasks.

In order to retry in case of connection failure, we can use the great `backoff`_ module.

.. code-block:: python

    # First define all your queries using a session argument:

    async def execute_query1(session):
        result = await session.execute(query1)
        print(result)

    async def execute_query2(session):
        result = await session.execute(query2)
        print(result)

    async def execute_subscription1(session):
        async for result in session.subscribe(subscription1):
            print(result)

    async def execute_subscription2(session):
        async for result in session.subscribe(subscription2):
            print(result)

    # Then create a couroutine which will connect to your API and run all your queries as tasks.
    # We use a `backoff` decorator to reconnect using exponential backoff in case of connection failure.

    @backoff.on_exception(backoff.expo, Exception, max_time=300)
    async def graphql_connection():

        transport = WebsocketsTransport(url="wss://YOUR_URL")

        client = Client(transport=transport, fetch_schema_from_transport=True)

        async with client as session:
            task1 = asyncio.create_task(execute_query1(session))
            task2 = asyncio.create_task(execute_query2(session))
            task3 = asyncio.create_task(execute_subscription1(session))
            task4 = asyncio.create_task(execute_subscription2(session))

            await asyncio.gather(task1, task2, task3, task4)

    asyncio.run(graphql_connection())

Subscriptions tasks can be stopped at any time by running

.. code-block:: python

    task.cancel()

.. _backoff: https://github.com/litl/backoff
