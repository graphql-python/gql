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

With :code:`reconnecting=True`, gql will use the `tenacity`_ module to repeatedly
try to connect with exponential backoff and jitter with a maximum delay of
60 seconds by default.

You can change the default reconnecting profile by providing your own
retry decorator (from tenacity) to the :code:`retry_connect` argument.

.. code-block:: python

    from tenacity import retry, retry_if_exception_type, wait_exponential

    # Here wait maximum 5 minutes between connection retries
    retry_connect = retry(
        # which exceptions should cause a retry (here: everything)
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(max=300),  # max wait time in seconds
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
retry decorator (from tenacity) to the :code:`retry_execute` argument.

.. code-block:: python

    from tenacity import (
        retry,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    # Here Only 3 tries for execute calls
    retry_execute = retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
    )
    session = await client.connect_async(
        reconnecting=True,
        retry_execute=retry_execute,
    )

If you don't want any retry on the execute calls, you can disable the retries
with :code:`retry_execute=False`

.. note::
    If you want to retry even with :code:`TransportQueryError` exceptions,
    then you need to make your own retry decorator (from tenacity) on your own method:

    .. code-block:: python

        from tenacity import (
            retry,
            retry_if_exception_type,
            stop_after_attempt,
            wait_exponential,
        )

        @retry(
            retry=retry_if_exception_type(Exception),
            stop=stop_after_attempt(3),
            wait=wait_exponential(),
        )
        async def execute_with_retry(session, query):
            return await session.execute(query)

Subscription retries
^^^^^^^^^^^^^^^^^^^^

There is no :code:`retry_subscribe` as it is not feasible with async generators.
If you want retries for your subscriptions, then you can do it yourself
with retry decorators (from tenacity) on your methods.

.. code-block:: python

    from tenacity import (
        retry,
        retry_if_exception_type,
        retry_unless_exception_type,
        stop_after_attempt,
        wait_exponential,
    )
    from gql.transport.exceptions import TransportQueryError

    @retry(
        retry=retry_if_exception_type(Exception)
        & retry_unless_exception_type(TransportQueryError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(),
    )
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
.. _tenacity: https://github.com/jd/tenacity
