Custom scalars and enums
========================

.. _custom_scalars:

Custom scalars
--------------

Scalar types represent primitive values at the leaves of a query.

GraphQL provides a number of built-in scalars (Int, Float, String, Boolean and ID), but a GraphQL backend
can add additional custom scalars to its schema to better express values in their data model.

For example, a schema can define the Datetime scalar to represent an ISO-8601 encoded date.

The schema will then only contain::

    scalar Datetime

When custom scalars are sent to the backend (as inputs) or from the backend (as outputs),
their values need to be serialized to be composed
of only built-in scalars, then at the destination the serialized values will be parsed again to
be able to represent the scalar in its local internal representation.

Because this serialization/unserialization is dependent on the language used at both sides, it is not
described in the schema and needs to be defined independently at both sides (client, backend).

A custom scalar value can have two different representations during its transport:

 - as a serialized value (usually as json):

    * in the results sent by the backend
    * in the variables sent by the client alongside the query

 - as "literal" inside the query itself sent by the client

To define a custom scalar, you need 3 methods:

 - a :code:`serialize` method used:

    * by the backend to serialize a custom scalar output in the result
    * by the client to serialize a custom scalar input in the variables

 - a :code:`parse_value` method used:

    * by the backend to unserialize custom scalars inputs in the variables sent by the client
    * by the client to unserialize custom scalars outputs from the results

 - a :code:`parse_literal` method used:

    * by the backend to unserialize custom scalars inputs inside the query itself

To define a custom scalar object, graphql-core provides the :code:`GraphQLScalarType` class
which contains the implementation of the above methods.

Example for Datetime:

.. code-block:: python

    from datetime import datetime
    from typing import Any, Dict, Optional

    from graphql import GraphQLScalarType, ValueNode
    from graphql.utilities import value_from_ast_untyped


    def serialize_datetime(value: Any) -> str:
        return value.isoformat()


    def parse_datetime_value(value: Any) -> datetime:
        return datetime.fromisoformat(value)


    def parse_datetime_literal(
        value_node: ValueNode, variables: Optional[Dict[str, Any]] = None
    ) -> datetime:
        ast_value = value_from_ast_untyped(value_node, variables)
        return parse_datetime_value(ast_value)


    DatetimeScalar = GraphQLScalarType(
        name="Datetime",
        serialize=serialize_datetime,
        parse_value=parse_datetime_value,
        parse_literal=parse_datetime_literal,
    )

If you get your schema from a "schema.graphql" file or from introspection,
then the generated schema in the gql Client will contain default :code:`GraphQLScalarType` instances
where the serialize and parse_value methods simply return the serialized value without modification.

In that case, if you want gql to parse custom scalars to a more useful Python representation,
or to serialize custom scalars variables from a Python representation,
then you can use the :func:`update_schema_scalars <gql.utilities.update_schema_scalars>`
or :func:`update_schema_scalar <gql.utilities.update_schema_scalar>` methods
to modify the definition of a scalar in your schema so that gql could do the parsing/serialization.

.. code-block:: python

    from gql.utilities import update_schema_scalar

    with open('path/to/schema.graphql') as f:
        schema_str = f.read()

    client = Client(schema=schema_str, ...)

    update_schema_scalar(client.schema, "Datetime", DatetimeScalar)

    # or update_schema_scalars(client.schema, [DatetimeScalar])

.. _enums:

Enums
-----

GraphQL Enum types are a special kind of scalar that is restricted to a particular set of allowed values.

For example, the schema may have a Color enum and contain::

    enum Color {
        RED
        GREEN
        BLUE
    }

Graphql-core provides the :code:`GraphQLEnumType` class to define an enum in the schema
(See `graphql-core schema building docs`_).

This class defines how the enum is serialized and parsed.

If you get your schema from a "schema.graphql" file or from introspection,
then the generated schema in the gql Client will contain default :code:`GraphQLEnumType` instances
which should serialize/parse enums to/from its String representation (the :code:`RED` enum
will be serialized to :code:`'RED'`).

You may want to parse enums to convert them to Python Enum types.
In that case, you can use the :func:`update_schema_enum <gql.utilities.update_schema_enum>`
to modify the default :code:`GraphQLEnumType` to use your defined Enum.

Example:

.. code-block:: python

    from enum import Enum
    from gql.utilities import update_schema_enum

    class Color(Enum):
        RED = 0
        GREEN = 1
        BLUE = 2

    with open('path/to/schema.graphql') as f:
        schema_str = f.read()

    client = Client(schema=schema_str, ...)

    update_schema_enum(client.schema, 'Color', Color)

Serializing Inputs
------------------

To provide custom scalars and/or enums in inputs with gql, you can:

- serialize the inputs manually
- let gql serialize the inputs using the custom scalars and enums defined in the schema

Manually
^^^^^^^^

You can serialize inputs yourself:

 - in the query itself
 - in variables

This has the advantage that you don't need a schema...

In the query
""""""""""""

- custom scalar:

.. code-block:: python

    query = gql(
        """{
        shiftDays(time: "2021-11-12T11:58:13.461161", days: 5)
    }"""
    )

- enum:

.. code-block:: python

    query = gql("{opposite(color: RED)}")

In a variable
"""""""""""""

- custom scalar:

.. code-block:: python

    query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

    variable_values = {
        "time": "2021-11-12T11:58:13.461161",
    }

    result = client.execute(query, variable_values=variable_values)

- enum:

.. code-block:: python

    query = gql(
        """
        query GetOppositeColor($color: Color) {
            opposite(color:$color)
        }"""
    )

    variable_values = {
        "color": 'RED',
    }

    result = client.execute(query, variable_values=variable_values)

Automatically
^^^^^^^^^^^^^

If you have custom scalar and/or enums defined in your schema
(See: :ref:`custom_scalars` and :ref:`enums`),
then you can request gql to serialize your variables automatically.

- use :code:`Client(..., serialize_variables=True)` to request serializing variables for all queries
- use :code:`execute(..., serialize_variables=True)` or :code:`subscribe(..., serialize_variables=True)` if
  you want gql to serialize the variables only for a single query.

Examples:

- custom scalars:

.. code-block:: python

    from gql.utilities import update_schema_scalars

    from .myscalars import DatetimeScalar

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:

        # We update the schema we got from introspection with our custom scalar type
        update_schema_scalars(session.client.schema, [DatetimeScalar])

        # In the query, the custom scalar in the input is set to a variable
        query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

        # the argument for time is a datetime instance
        variable_values = {"time": datetime.now()}

        # we execute the query with serialize_variables set to True
        result = await session.execute(
            query, variable_values=variable_values, serialize_variables=True
        )

- enums:

.. code-block:: python

    from gql.utilities import update_schema_enum

    from .myenums import Color

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:

        # We update the schema we got from introspection with our custom enum
        update_schema_enum(session.client.schema, 'Color', Color)

        # In the query, the enum in the input is set to a variable
        query = gql(
            """
            query GetOppositeColor($color: Color) {
                opposite(color:$color)
            }"""
        )

        # the argument for time is an instance of our Enum type
        variable_values = {
            "color": Color.RED,
        }

        # we execute the query with serialize_variables set to True
        result = client.execute(
            query, variable_values=variable_values, serialize_variables=True
        )

Parsing output
--------------

By default, gql returns the serialized result from the backend without parsing
(except json unserialization to Python default types).

if you want to convert the result of custom scalars to custom objects,
you can request gql to parse the results.

- use :code:`Client(..., parse_results=True)` to request parsing for all queries
- use :code:`execute(..., parse_result=True)` or :code:`subscribe(..., parse_result=True)` if
  you want gql to parse only the result of a single query.

Same example as above, with result parsing enabled:

.. code-block:: python

    from gql.utilities import update_schema_scalars

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:

        update_schema_scalars(session.client.schema, [DatetimeScalar])

        query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

        variable_values = {"time": datetime.now()}

        result = await session.execute(
            query,
            variable_values=variable_values,
            serialize_variables=True,
            parse_result=True,
        )

        # now result["time"] type is a datetime instead of string

.. _graphql-core schema building docs: https://graphql-core-3.readthedocs.io/en/latest/usage/schema.html
