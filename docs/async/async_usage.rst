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
