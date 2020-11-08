Compose queries dynamically
===========================

Instead of providing the GraphQL queries as a Python String, it is also possible to create GraphQL queries dynamically.
Using the :mod:`DSL module <gql.dsl>`, we can create a query using a Domain Specific Language which is created from the schema.

The following code:

.. code-block:: python

    ds = DSLSchema(StarWarsSchema)

    query = dsl_gql(
        ds.Query.hero.select(
            ds.Character.id,
            ds.Character.name,
            ds.Character.friends.select(ds.Character.name),
        )
    )

will generate a query equivalent to:

.. code-block:: python

    query = gql("""
        query {
          hero {
            id
            name
            friends {
              name
            }
          }
        }
    """)

How to use
----------

First generate the root using the :class:`DSLSchema <gql.dsl.DSLSchema>`::

    ds = DSLSchema(client.schema)

Then use auto-generated attributes of the :code:`ds` instance
to get a root type (Query, Mutation or Subscription).
This will generate a :class:`DSLType <gql.dsl.DSLType>` instance::

    ds.Query

From this root type, you use auto-generated attributes to get a field.
This will generate a :class:`DSLField <gql.dsl.DSLField>` instance::

    ds.Query.hero

hero is a GraphQL object type and needs children fields. By default,
there is no children fields selected. To select the fields that you want
in your query, you use the :meth:`select <gql.dsl.DSLField.select>` method.

To generate the children fields, we use the same method as above to auto-generate the fields
from the :code:`ds` instance
(ie :code:`ds.Character.name` is the field `name` of the type `Character`)::

    ds.Query.hero.select(ds.Character.name)

The select method return the same instance, so it is possible to chain the calls::

    ds.Query.hero.select(ds.Character.name).select(ds.Character.id)

Or do it sequencially::

    hero_query = ds.Query.hero

    hero_query.select(ds.Character.name)
    hero_query.select(ds.Character.id)

As you can select children fields of any object type, you can construct your complete query tree::

    ds.Query.hero.select(
        ds.Character.id,
        ds.Character.name,
        ds.Character.friends.select(ds.Character.name),
    )

Once your query is completed and you have selected all the fields you want,
use the :func:`dsl_gql <gql.dsl.dsl_gql>` function to convert your query into
a document which will be able to get executed in the client or a session::

    query = dsl_gql(
        ds.Query.hero.select(
            ds.Character.id,
            ds.Character.name,
            ds.Character.friends.select(ds.Character.name),
        )
    )

    result = client.execute(query)

Arguments
^^^^^^^^^

It is possible to add arguments to any field simply by calling it
with the required arguments::

    ds.Query.human(id="1000").select(ds.Human.name)

It can also be done using the :meth:`args <gql.dsl.DSLField.args>` method::

    ds.Query.human.args(id="1000").select(ds.Human.name)

Alias
^^^^^

You can set an alias of a field using the :meth:`alias <gql.dsl.DSLField.alias>` method::

    ds.Query.human.args(id=1000).alias("luke").select(ds.Character.name)

Mutations
^^^^^^^^^

It works the same way for mutations. Example::

    query = dsl_gql(
        ds.Mutation.createReview.args(
            episode=6, review={"stars": 5, "commentary": "This is a great movie!"}
        ).select(ds.Review.stars, ds.Review.commentary)
    )

Multiple requests
^^^^^^^^^^^^^^^^^

It is possible to create a document with multiple requests::

    query = dsl_gql(
        ds.Query.hero.select(ds.Character.name),
        ds.Query.hero(episode=5).alias("hero_of_episode_5").select(ds.Character.name),
    )

But you have to take care that the root type is always the same. It is not possible
to mix queries and mutations for example.

Executable examples
-------------------

Async example
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/aiohttp_async_dsl.py

Sync example
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/requests_sync_dsl.py

