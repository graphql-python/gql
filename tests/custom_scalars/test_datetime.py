from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import pytest
from graphql.error import GraphQLError
from graphql.language import ValueNode
from graphql.pyutils import inspect
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLList,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.utilities import value_from_ast_untyped

from gql import Client, gql


def serialize_datetime(value: Any) -> str:
    if not isinstance(value, datetime):
        raise GraphQLError("Cannot serialize datetime value: " + inspect(value))
    return value.isoformat()


def parse_datetime_value(value: Any) -> datetime:

    if isinstance(value, str):
        try:
            # Note: a more solid custom scalar should use dateutil.parser.isoparse
            #       Not using it here in the test to avoid adding another dependency
            return datetime.fromisoformat(value)
        except Exception:
            raise GraphQLError("Cannot parse datetime value : " + inspect(value))

    else:
        raise GraphQLError("Cannot parse datetime value: " + inspect(value))


def parse_datetime_literal(
    value_node: ValueNode, variables: Optional[Dict[str, Any]] = None
) -> datetime:
    ast_value = value_from_ast_untyped(value_node, variables)
    if not isinstance(ast_value, str):
        raise GraphQLError("Cannot parse literal datetime value: " + inspect(ast_value))

    return parse_datetime_value(ast_value)


DatetimeScalar = GraphQLScalarType(
    name="Datetime",
    serialize=serialize_datetime,
    parse_value=parse_datetime_value,
    parse_literal=parse_datetime_literal,
)


def resolve_shift_days(root, _info, time, days):
    return time + timedelta(days=days)


def resolve_latest(root, _info, times):
    return max(times)


def resolve_seconds(root, _info, interval):
    print(f"interval={interval!r}")
    return (interval["end"] - interval["start"]).total_seconds()


IntervalInputType = GraphQLInputObjectType(
    "IntervalInput",
    fields={
        "start": GraphQLInputField(DatetimeScalar),
        "end": GraphQLInputField(DatetimeScalar),
    },
)

queryType = GraphQLObjectType(
    name="RootQueryType",
    fields={
        "shiftDays": GraphQLField(
            DatetimeScalar,
            args={
                "time": GraphQLArgument(DatetimeScalar),
                "days": GraphQLArgument(GraphQLInt),
            },
            resolve=resolve_shift_days,
        ),
        "latest": GraphQLField(
            DatetimeScalar,
            args={"times": GraphQLArgument(GraphQLList(DatetimeScalar))},
            resolve=resolve_latest,
        ),
        "seconds": GraphQLField(
            GraphQLInt,
            args={"interval": GraphQLArgument(IntervalInputType)},
            resolve=resolve_seconds,
        ),
    },
)

schema = GraphQLSchema(query=queryType)


@pytest.mark.skipif(
    not hasattr(datetime, "fromisoformat"), reason="fromisoformat is new in Python 3.7+"
)
def test_shift_days():

    client = Client(schema=schema, parse_results=True, serialize_variables=True)

    now = datetime.fromisoformat("2021-11-12T11:58:13.461161")

    query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

    variable_values = {
        "time": now,
    }

    result = client.execute(query, variable_values=variable_values)

    print(result)

    assert result["shiftDays"] == datetime.fromisoformat("2021-11-17T11:58:13.461161")


@pytest.mark.skipif(
    not hasattr(datetime, "fromisoformat"), reason="fromisoformat is new in Python 3.7+"
)
def test_shift_days_serialized_manually_in_query():

    client = Client(schema=schema)

    query = gql(
        """{
        shiftDays(time: "2021-11-12T11:58:13.461161", days: 5)
    }"""
    )

    result = client.execute(query, parse_result=True)

    print(result)

    assert result["shiftDays"] == datetime.fromisoformat("2021-11-17T11:58:13.461161")


@pytest.mark.skipif(
    not hasattr(datetime, "fromisoformat"), reason="fromisoformat is new in Python 3.7+"
)
def test_shift_days_serialized_manually_in_variables():

    client = Client(schema=schema, parse_results=True)

    query = gql("query shift5days($time: Datetime) {shiftDays(time: $time, days: 5)}")

    variable_values = {
        "time": "2021-11-12T11:58:13.461161",
    }

    result = client.execute(query, variable_values=variable_values)

    print(result)

    assert result["shiftDays"] == datetime.fromisoformat("2021-11-17T11:58:13.461161")


@pytest.mark.skipif(
    not hasattr(datetime, "fromisoformat"), reason="fromisoformat is new in Python 3.7+"
)
def test_latest():

    client = Client(schema=schema, parse_results=True)

    now = datetime.fromisoformat("2021-11-12T11:58:13.461161")
    in_five_days = datetime.fromisoformat("2021-11-17T11:58:13.461161")

    query = gql("query latest($times: [Datetime!]!) {latest(times: $times)}")

    variable_values = {
        "times": [now, in_five_days],
    }

    result = client.execute(
        query, variable_values=variable_values, serialize_variables=True
    )

    print(result)

    assert result["latest"] == in_five_days


@pytest.mark.skipif(
    not hasattr(datetime, "fromisoformat"), reason="fromisoformat is new in Python 3.7+"
)
def test_seconds():
    client = Client(schema=schema)

    now = datetime.fromisoformat("2021-11-12T11:58:13.461161")
    in_five_days = datetime.fromisoformat("2021-11-17T11:58:13.461161")

    query = gql(
        "query seconds($interval: IntervalInput) {seconds(interval: $interval)}"
    )

    variable_values = {"interval": {"start": now, "end": in_five_days}}

    result = client.execute(
        query, variable_values=variable_values, serialize_variables=True
    )

    print(result)

    assert result["seconds"] == 432000
