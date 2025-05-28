.. _batching_requests:

Batching requests
=================

If you need to send multiple GraphQL queries to a backend,
and if the backend supports batch requests,
then you might want to send those requests in a batch instead of
making multiple execution requests.

.. warning::
    - Some backends do not support batch requests
    - File uploads and subscriptions are not supported with batch requests

Batching requests manually
^^^^^^^^^^^^^^^^^^^^^^^^^^

To execute a batch of requests manually:

- First Make a list of :class:`GraphQLRequest <gql.GraphQLRequest>` objects, containing:
   * your GraphQL query
   * Optional variable_values
   * Optional operation_name

.. code-block:: python

    request1 = gql("""
        query getContinents {
          continents {
            code
            name
          }
        }
        """
    )

    request2 = GraphQLRequest("""
        query getContinentName ($code: ID!) {
          continent (code: $code) {
            name
          }
        }
        """,
        variable_values={
          "code": "AF",
        },
    )

    requests = [request1, request2]

- Then use one of the `execute_batch` methods, either on Client,
  or in a sync or async session

**Sync**:

.. code-block:: python

    transport = RequestsHTTPTransport(url=url)
    # Or transport = HTTPXTransport(url=url)

    with Client(transport=transport) as session:

        results = session.execute_batch(requests)

        result1 = results[0]
        result2 = results[1]

**Async**:

.. code-block:: python

    transport = AIOHTTPTransport(url=url)
    # Or transport = HTTPXAsyncTransport(url=url)

    async with Client(transport=transport) as session:

        results = await session.execute_batch(requests)

        result1 = results[0]
        result2 = results[1]

.. note::
    If any request in the batch returns an error, then a TransportQueryError will be raised
    with the first error found.

Automatic Batching of requests
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If your code execute multiple requests independently in a short time
(either from different threads in sync code, or from different asyncio tasks in async code),
then you can use gql automatic batching of request functionality.

You define a :code:`batching_interval` in your :class:`Client <gql.Client>`
and each time a new execution request is received through an `execute` method,
we will wait that interval (in seconds) for other requests to arrive
before sending all the requests received in that interval in a single batch.
