.. _schema_validation:

Schema validation
=================

It a GraphQL schema is provided, gql will validate the queries locally before sending them to the backend.
If no schema is provided, gql will send the query to the backend without local validation.

You can either provide a schema yourself, or you can request gql to get the schema
from the backend using `introspection`_.

Using a provided schema
-----------------------

The schema can be provided as a String (which is usually stored in a .graphql file):

.. code-block:: python

    with open('path/to/schema.graphql') as f:
        schema_str = f.read()

    client = Client(schema=schema_str)

OR can be created using python classes:

.. code-block:: python

    from .someSchema import SampleSchema
    # SampleSchema is an instance of GraphQLSchema

    client = Client(schema=SampleSchema)

See `tests/starwars/schema.py`_ for an example of such a schema.

Using introspection
-------------------

In order to get the schema directly from the GraphQL Server API using the transport, you need
to set the `fetch_schema_from_transport` argument of Client to True, and the client will
fetch the schema before the execution of the first query.

.. _introspection: https://graphql.org/learn/introspection
.. _tests/starwars/schema.py: https://github.com/graphql-python/gql/blob/master/tests/starwars/schema.py
