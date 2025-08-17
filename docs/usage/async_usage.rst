.. _async_usage:

Async usage
===========

On previous versions of GQL, the code was `sync` only , it means that when you ran
`execute` on the Client, you could do nothing else in the current Thread and had to wait for
an answer or a timeout from the backend to continue. The only http library was `requests`, allowing only sync usage.

From the version 3 of GQL, we support `sync` and `async` :ref:`transports <transports>` using `asyncio`_.

With the :ref:`async transports <async_transports>`, there is now the possibility to execute GraphQL requests
asynchronously, :ref:`allowing to execute multiple requests in parallel if needed <async_advanced_usage>`.

If you don't care or need async functionality, it is still possible, with :ref:`async transports <async_transports>`,
to run the `execute` or `subscribe` methods directly from the Client
(as described in the :ref:`Sync Usage <sync_usage>` example) and GQL will execute the request
in a synchronous manner by running an asyncio event loop itself.

This won't work though if you already have an asyncio event loop running. In that case you should use the async
methods.

Example
-------

If you use an :ref:`async transport <async_transports>`, you can use GQL asynchronously using `asyncio`_.

* put your code in an asyncio coroutine (method starting with :code:`async def`)
* use :code:`async with client as session:` to connect to the backend and provide a session instance
* use the :code:`await` keyword to execute requests: :code:`await session.execute(...)`
* then run your coroutine in an asyncio event loop by running :code:`asyncio.run`

.. literalinclude:: ../code_examples/aiohttp_async.py

IPython
-------

.. warning::

    On some Python environments, like :emphasis:`Jupyter` or :emphasis:`Spyder`,
    which are using :emphasis:`IPython`,
    an asyncio event loop is already created for you by the environment.

In this case, running the above code might generate the following error::

    RuntimeError: asyncio.run() cannot be called from a running event loop

If that happens, depending on the environment,
you should replace :code:`asyncio.run(main())` by either:

.. code-block:: python

    await main()

OR:

.. code-block:: python

    loop = asyncio.get_running_loop()
    loop.create_task(main())

.. _asyncio: https://docs.python.org/3/library/asyncio.html
