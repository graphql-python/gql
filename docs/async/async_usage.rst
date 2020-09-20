.. _async_usage:

Async Usage
===========

If you use an :ref:`async transport <async_transports>`, you can use GQL asynchronously using `asyncio`_.

* put your code in an asyncio coroutine (method starting with :code:`async def`)
* use :code:`async with client as session:` to connect to the backend and provide a session instance
* use the :code:`await` keyword to execute requests: :code:`await session.execute(...)`
* then run your coroutine in an asyncio event loop by running :code:`asyncio.run`

Example:

.. literalinclude:: ../code_examples/aiohttp_async.py

.. _asyncio: https://docs.python.org/3/library/asyncio.html
