.. _async_permanent_session:

Async permanent session
=======================

Sometimes you want to have a single permanent reconnecting async session to a GraphQL backend,
and that can be `difficult to manage`_ manually with the :code:`async with client as session` syntax.

It is now possible to have a single reconnecting session using the
:meth:`connect_async <gql.Client.connect_async>` method of Client
with a :code:`reconnecting=True` argument.

.. code-block:: python

    # Create a session from the client which will reconnect automatically.
    # This session can be kept in a class for example to provide a way
    # to execute GraphQL queries from many different places
    session = await client.connect_async(reconnecting=True)

    # You can run execute or subscribe method on this session
    result = await session.execute(query)

    # When you want the connection to close (for cleanup),
    # you call close_async
    await client.close_async()


When you use :code:`reconnecting=True`, gql will watch the exceptions generated
during the execute and subscribe calls and, if it detects a TransportClosed exception
(indicating that the link to the underlying transport is broken),
it will try to reconnect to the backend again.

Retries
-------

Connection retries
^^^^^^^^^^^^^^^^^^

With :code:`reconnecting=True`, gql will use the `backoff`_ module to repeatedly try to connect with
exponential backoff and jitter with a maximum delay of 60 seconds by default.

You can change the default reconnecting profile by providing your own
backoff decorator to the :code:`retry_connect` argument.

.. code-block:: python

    # Here wait maximum 5 minutes between connection retries
    retry_connect = backoff.on_exception(
        backoff.expo,  # wait generator (here: exponential backoff)
        Exception,     # which exceptions should cause a retry (here: everything)
        max_value=300, # max wait time in seconds
    )
    session = await client.connect_async(
        reconnecting=True,
        retry_connect=retry_connect,
    )

Execution retries
^^^^^^^^^^^^^^^^^

With :code:`reconnecting=True`, by default we will also retry up to 5 times
when an exception happens during an execute call (to manage a possible loss in the connection
to the transport).

There is no retry in case of a :code:`TransportQueryError` exception as it indicates that
the connection to the backend is working correctly.

You can change the default execute retry profile by providing your own
backoff decorator to the :code:`retry_execute` argument.

.. code-block:: python

    # Here Only 3 tries for execute calls
    retry_execute = backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=3,
        giveup=lambda e: isinstance(e, TransportQueryError),
    )
    session = await client.connect_async(
        reconnecting=True,
        retry_execute=retry_execute,
    )

If you don't want any retry on the execute calls, you can disable the retries with :code:`retry_execute=False`

Subscription retries
^^^^^^^^^^^^^^^^^^^^

There is no :code:`retry_subscribe` as it is not feasible with async generators.
If you want retries for your subscriptions, then you can do it yourself
with backoff decorators on your methods.

.. code-block:: python

    @backoff.on_exception(backoff.expo,
                          Exception,
                          max_tries=3,
                          giveup=lambda e: isinstance(e, TransportQueryError))
    async def execute_subscription1(session):
        async for result in session.subscribe(subscription1):
            print(result)

FastAPI example
---------------

.. literalinclude:: ../code_examples/fastapi_async.py

Console example
---------------

.. literalinclude:: ../code_examples/console_async.py

.. _difficult to manage: https://github.com/graphql-python/gql/issues/179
.. _backoff: https://github.com/litl/backoff
