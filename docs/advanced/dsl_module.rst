Compose queries dynamically
===========================

Instead of providing the GraphQL queries as a Python String, it is also possible to create GraphQL queries dynamically.
Using the DSL module, we can create a query using a Domain Specific Language which is created from the schema.

.. code-block:: python

    from gql.dsl import DSLSchema

    client = Client(schema=StarWarsSchema)
    ds = DSLSchema(client)

    query_dsl = ds.Query.hero.select(
        ds.Character.id,
        ds.Character.name,
        ds.Character.friends.select(ds.Character.name,),
    )

will create a query equivalent to:

.. code-block:: python

    hero {
      id
      name
      friends {
        name
      }
    }

.. warning::

    Please note that the DSL module is still considered experimental in GQL 3 and is subject to changes
