Execution on a local schema
===========================

It is also possible to execute queries against a local schema (so without a transport), even
if it is not really useful except maybe for testing.

.. code-block:: python

    from gql import gql, Client

    from .someSchema import SampleSchema

    client = Client(schema=SampleSchema)

    query = gql('''
        {
          hello
        }
    ''')

    result = client.execute(query)

See `tests/starwars/test_query.py`_ for an example

.. _tests/starwars/test_query.py: https://github.com/graphql-python/gql/blob/master/tests/starwars/test_query.py
