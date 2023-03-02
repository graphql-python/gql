Logging
=======

GQL uses the python `logging`_ module.

In order to debug a problem, you can enable logging to see the messages exchanged between the client and the server.
To do that, set the loglevel at **INFO** at the beginning of your code:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.INFO)

For even more logs, you can set the loglevel at **DEBUG**:

.. code-block:: python

    import logging
    logging.basicConfig(level=logging.DEBUG)

Disabling logs
--------------

By default, the logs for the transports are quite verbose.

On the **INFO** level, all the messages between the frontend and the backend are logged which can
be difficult to read especially when it fetches the schema from the transport.

It is possible to disable the logs only for a specific gql transport by setting a higher
log level for this transport (**WARNING** for example) so that the other logs of your program are not affected.

For this, you should import the logger from the transport file and set the level on this logger.

For the RequestsHTTPTransport:

.. code-block:: python

    from gql.transport.requests import log as requests_logger
    requests_logger.setLevel(logging.WARNING)

For the WebsocketsTransport:

.. code-block:: python

    from gql.transport.websockets import log as websockets_logger
    websockets_logger.setLevel(logging.WARNING)

.. _logging: https://docs.python.org/3/howto/logging.html
