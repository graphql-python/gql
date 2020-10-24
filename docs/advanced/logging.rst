Logging
=======

GQL use the python `logging`_ module.

In order to debug a problem, you can enable logging to see the messages exchanged between the client and the server.
To do that, set the loglevel at **INFO** at the beginning of your code:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.INFO)

For even more logs, you can set the loglevel at **DEBUG**:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.DEBUG)

.. _logging: https://docs.python.org/3/howto/logging.html
