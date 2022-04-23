Compose queries dynamically
===========================

Instead of providing the GraphQL queries as a Python String, it is also possible to create GraphQL queries dynamically.
Using the :mod:`DSL module <gql.dsl>`, we can create a query using a Domain Specific Language which is created from the schema.

The following code:

.. code-block:: python

    ds = DSLSchema(StarWarsSchema)

    query = dsl_gql(
        DSLQuery(
            ds.Query.hero.select(
                ds.Character.id,
                ds.Character.name,
                ds.Character.friends.select(ds.Character.name),
            )
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

Once your root query fields are defined, you can put them in an operation using
:class:`DSLQuery <gql.dsl.DSLQuery>`,
:class:`DSLMutation <gql.dsl.DSLMutation>` or
:class:`DSLSubscription <gql.dsl.DSLSubscription>`::

    DSLQuery(
        ds.Query.hero.select(
            ds.Character.id,
            ds.Character.name,
            ds.Character.friends.select(ds.Character.name),
        )
    )


Once your operations are defined,
use the :func:`dsl_gql <gql.dsl.dsl_gql>` function to convert your operations into
a document which will be able to get executed in the client or a session::

    query = dsl_gql(
        DSLQuery(
            ds.Query.hero.select(
                ds.Character.id,
                ds.Character.name,
                ds.Character.friends.select(ds.Character.name),
            )
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

.. note::
    If your argument name is a Python keyword (for, in, from, ...), you will receive a
    SyntaxError (See `issue #308`_). To fix this, you can provide the arguments by unpacking a dictionary.

    For example, instead of using :code:`from=5`, you can use :code:`**{"from":5}`

Aliases
^^^^^^^

You can set an alias of a field using the :meth:`alias <gql.dsl.DSLField.alias>` method::

    ds.Query.human.args(id=1000).alias("luke").select(ds.Character.name)

It is also possible to set the alias directly using keyword arguments of an operation::

    DSLQuery(
        luke=ds.Query.human.args(id=1000).select(ds.Character.name)
    )

Or using keyword arguments in the :meth:`select <gql.dsl.DSLField.select>` method::

    ds.Query.hero.select(
        my_name=ds.Character.name
    )

Mutations
^^^^^^^^^

For the mutations, you need to start from root fields starting from :code:`ds.Mutation`
then you need to create the GraphQL operation using the class
:class:`DSLMutation <gql.dsl.DSLMutation>`. Example::

    query = dsl_gql(
        DSLMutation(
            ds.Mutation.createReview.args(
                episode=6, review={"stars": 5, "commentary": "This is a great movie!"}
            ).select(ds.Review.stars, ds.Review.commentary)
        )
    )

Variable arguments
^^^^^^^^^^^^^^^^^^

To provide variables instead of argument values directly for an operation, you have to:

* Instantiate a :class:`DSLVariableDefinitions <gql.dsl.DSLVariableDefinitions>`::

    var = DSLVariableDefinitions()

* From this instance you can generate :class:`DSLVariable <gql.dsl.DSLVariable>` instances
  and provide them as the value of the arguments::

    ds.Mutation.createReview.args(review=var.review, episode=var.episode)

* Once the operation has been defined, you have to save the variable definitions used
  in it::

    operation.variable_definitions = var

The following code:

.. code-block:: python

    var = DSLVariableDefinitions()
    op = DSLMutation(
        ds.Mutation.createReview.args(review=var.review, episode=var.episode).select(
            ds.Review.stars, ds.Review.commentary
        )
    )
    op.variable_definitions = var
    query = dsl_gql(op)

will generate a query equivalent to::

    mutation ($review: ReviewInput, $episode: Episode) {
      createReview(review: $review, episode: $episode) {
        stars
        commentary
      }
    }

Variable arguments with a default value
"""""""""""""""""""""""""""""""""""""""

If you want to provide a **default value** for your variable, you can use
the :code:`default` method on a variable.

The following code:

.. code-block:: python

    var = DSLVariableDefinitions()
    op = DSLMutation(
        ds.Mutation.createReview.args(
            review=var.review.default({"stars": 5, "commentary": "Wow!"}),
            episode=var.episode,
        ).select(ds.Review.stars, ds.Review.commentary)
    )
    op.variable_definitions = var
    query = dsl_gql(op)

will generate a query equivalent to::

    mutation ($review: ReviewInput = {stars: 5, commentary: "Wow!"}, $episode: Episode) {
      createReview(review: $review, episode: $episode) {
        stars
        commentary
      }
    }

Subscriptions
^^^^^^^^^^^^^

For the subscriptions, you need to start from root fields starting from :code:`ds.Subscription`
then you need to create the GraphQL operation using the class
:class:`DSLSubscription <gql.dsl.DSLSubscription>`. Example::

    query = dsl_gql(
        DSLSubscription(
            ds.Subscription.reviewAdded(episode=6).select(ds.Review.stars, ds.Review.commentary)
        )
    )

Multiple fields in an operation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to create an operation with multiple fields::

    DSLQuery(
        ds.Query.hero.select(ds.Character.name),
        hero_of_episode_5=ds.Query.hero(episode=5).select(ds.Character.name),
    )

Operation name
^^^^^^^^^^^^^^

You can set the operation name of an operation using a keyword argument
to :func:`dsl_gql <gql.dsl.dsl_gql>`::

    query = dsl_gql(
        GetHeroName=DSLQuery(ds.Query.hero.select(ds.Character.name))
    )

will generate the request::

    query GetHeroName {
        hero {
            name
        }
    }

Multiple operations in a document
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to create an Document with multiple operations::

    query = dsl_gql(
        operation_name_1=DSLQuery( ... ),
        operation_name_2=DSLQuery( ... ),
        operation_name_3=DSLMutation( ... ),
    )

Fragments
^^^^^^^^^

To define a `Fragment`_, you have to:

* Instantiate a :class:`DSLFragment <gql.dsl.DSLFragment>` with a name::

    name_and_appearances = DSLFragment("NameAndAppearances")

* Provide the GraphQL type of the fragment with the
  :meth:`on <gql.dsl.DSLFragment.on>` method::

    name_and_appearances.on(ds.Character)

* Add children fields using the :meth:`select <gql.dsl.DSLFragment.select>` method::

    name_and_appearances.select(ds.Character.name, ds.Character.appearsIn)

Once your fragment is defined, to use it you should:

* select it as a field somewhere in your query::

    query_with_fragment = DSLQuery(ds.Query.hero.select(name_and_appearances))

* add it as an argument of :func:`dsl_gql <gql.dsl.dsl_gql>` with your query::

    query = dsl_gql(name_and_appearances, query_with_fragment)

The above example will generate the following request::

    fragment NameAndAppearances on Character {
        name
        appearsIn
    }

    {
        hero {
            ...NameAndAppearances
        }
    }

Inline Fragments
^^^^^^^^^^^^^^^^

To define an `Inline Fragment`_, you have to:

* Instantiate a :class:`DSLInlineFragment <gql.dsl.DSLInlineFragment>`::

    human_fragment = DSLInlineFragment()

* Provide the GraphQL type of the fragment with the
  :meth:`on <gql.dsl.DSLInlineFragment.on>` method::

    human_fragment.on(ds.Human)

* Add children fields using the :meth:`select <gql.dsl.DSLInlineFragment.select>` method::

    human_fragment.select(ds.Human.homePlanet)

Once your inline fragment is defined, to use it you should:

* select it as a field somewhere in your query::

    query_with_inline_fragment = ds.Query.hero.args(episode=6).select(
        ds.Character.name,
        human_fragment
    )

The above example will generate the following request::

    hero(episode: JEDI) {
        name
        ... on Human {
          homePlanet
        }
    }

Note: because the :meth:`on <gql.dsl.DSLInlineFragment.on>` and
:meth:`select <gql.dsl.DSLInlineFragment.select>` methods return :code:`self`,
this can be written in a concise manner::

    query_with_inline_fragment = ds.Query.hero.args(episode=6).select(
        ds.Character.name,
        DSLInlineFragment().on(ds.Human).select(ds.Human.homePlanet)
    )

Meta-fields
^^^^^^^^^^^

To define meta-fields (:code:`__typename`, :code:`__schema` and :code:`__type`),
you can use the :class:`DSLMetaField <gql.dsl.DSLMetaField>` class::

    query = ds.Query.hero.select(
        ds.Character.name,
        DSLMetaField("__typename")
    )

Executable examples
-------------------

Async example
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/aiohttp_async_dsl.py

Sync example
^^^^^^^^^^^^^

.. literalinclude:: ../code_examples/requests_sync_dsl.py

.. _Fragment: https://graphql.org/learn/queries/#fragments
.. _Inline Fragment: https://graphql.org/learn/queries/#inline-fragments
.. _issue #308: https://github.com/graphql-python/gql/issues/308
