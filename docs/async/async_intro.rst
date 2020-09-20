On previous versions of GQL, the code was `sync` only , it means that when you ran
`execute` on the Client, you could do nothing else in the current Thread and had to wait for
an answer or a timeout from the backend to continue. The only http library was `requests`, allowing only sync usage.

From the version 3 of GQL, we support `sync` and `async` :ref:`transports <transports>` using `asyncio`_.

With the :ref:`async transports <async_transports>`, there is now the possibility to execute GraphQL requests
asynchronously, :ref:`allowing to execute multiple requests in parallel if needed <async_advanced_usage>`.

If you don't care or need async functionality, it is still possible, with :ref:`async transports <async_transports>`,
to run the `execute` or `subscribe` methods directly from the Client
(as described in the :ref:`Basic Usage <basic_usage>` example) and GQL will execute the request
in a synchronous manner by running an asyncio event loop itself.

This won't work though if you already have an asyncio event loop running. In that case you should use
:ref:`Async Usage <async_usage>`

.. _asyncio: https://docs.python.org/3/library/asyncio.html
