Custom Scalars
==============

Scalar types represent primitive values at the leaves of a query.

GraphQL provides a number of built-in scalars (Int, Float, String, Boolean and ID), but a GraphQL backend
can add additional custom scalars to its schema to better express values in their data model.

For example, a schema can define the Datetime scalar to represent an ISO-8601 encoded date.

The schema will then only contain:

.. code-block:: python

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

To define a custom scalar object, we define a :code:`GraphQLScalarType` from graphql-core with
its name and the implementation of the above methods.

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

Custom Scalars in inputs
------------------------

To provide custom scalars in input with gql, you can:

- serialize the scalar yourself as "literal" in the query:

.. code-block:: python

    query = gql(
        """{
        shiftDays(time: "2021-11-12T11:58:13.461161", days: 5)
    }"""
    )

- serialize the scalar yourself in a variable:

.. code-block:: python

    query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

    variable_values = {
        "time": "2021-11-12T11:58:13.461161",
    }

    result = client.execute(query, variable_values=variable_values)

- add a custom scalar to the schema with :func:`update_schema_scalars <gql.utilities.update_schema_scalars>`
  and execute the query with :code:`serialize_variables=True`
  and gql will serialize the variable values from a Python object representation.

For this, you need to provide a schema or set :code:`fetch_schema_from_transport=True`
in the client to request the schema from the backend.

.. code-block:: python

    from gql.utilities import update_schema_scalars

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:

        update_schema_scalars(session.client.schema, [DatetimeScalar])

        query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

        variable_values = {"time": datetime.now()}

        result = await session.execute(
            query, variable_values=variable_values, serialize_variables=True
        )

        # result["time"] is a string

Custom Scalars in output
------------------------

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
