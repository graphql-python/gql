from enum import Enum

import pytest
from graphql import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLField,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
)

from gql import Client, gql
from gql.utilities import update_schema_enum


class Color(Enum):
    RED = 0
    GREEN = 1
    BLUE = 2
    YELLOW = 3
    CYAN = 4
    MAGENTA = 5


RED = Color.RED
GREEN = Color.GREEN
BLUE = Color.BLUE
YELLOW = Color.YELLOW
CYAN = Color.CYAN
MAGENTA = Color.MAGENTA

ALL_COLORS = [c for c in Color]

ColorType = GraphQLEnumType("Color", {c.name: c for c in Color})


def resolve_opposite(_root, _info, color):
    opposite_colors = {
        RED: CYAN,
        GREEN: MAGENTA,
        BLUE: YELLOW,
        YELLOW: BLUE,
        CYAN: RED,
        MAGENTA: GREEN,
    }

    return opposite_colors[color]


def resolve_all(_root, _info):
    return ALL_COLORS


list_of_list_of_list = [[[RED, GREEN], [GREEN, BLUE]], [[YELLOW, CYAN], [MAGENTA, RED]]]


def resolve_list_of_list_of_list(_root, _info):
    return list_of_list_of_list


def resolve_list_of_list(_root, _info):
    return list_of_list_of_list[0]


def resolve_list(_root, _info):
    return list_of_list_of_list[0][0]


queryType = GraphQLObjectType(
    name="RootQueryType",
    fields={
        "all": GraphQLField(GraphQLList(ColorType), resolve=resolve_all,),
        "opposite": GraphQLField(
            ColorType,
            args={"color": GraphQLArgument(ColorType)},
            resolve=resolve_opposite,
        ),
        "list_of_list_of_list": GraphQLField(
            GraphQLNonNull(
                GraphQLList(
                    GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLList(ColorType))))
                )
            ),
            resolve=resolve_list_of_list_of_list,
        ),
        "list_of_list": GraphQLField(
            GraphQLNonNull(GraphQLList(GraphQLNonNull(GraphQLList(ColorType)))),
            resolve=resolve_list_of_list,
        ),
        "list": GraphQLField(
            GraphQLNonNull(GraphQLList(ColorType)), resolve=resolve_list,
        ),
    },
)

schema = GraphQLSchema(query=queryType)


def test_parse_value_enum():

    result = ColorType.parse_value("RED")

    print(result)

    assert isinstance(result, Color)
    assert result is RED


def test_serialize_enum():

    result = ColorType.serialize(RED)

    print(result)

    assert result == "RED"


def test_get_all_colors():

    query = gql("{all}")

    client = Client(schema=schema, parse_results=True)

    result = client.execute(query)

    print(result)

    all_colors = result["all"]

    assert all_colors == ALL_COLORS


def test_opposite_color_literal():

    client = Client(schema=schema, parse_results=True)

    query = gql("{opposite(color: RED)}")

    result = client.execute(query)

    print(result)

    opposite_color = result["opposite"]

    assert isinstance(opposite_color, Color)
    assert opposite_color == CYAN


def test_opposite_color_variable_serialized_manually():

    client = Client(schema=schema, parse_results=True)

    query = gql(
        """
        query GetOppositeColor($color: Color) {
            opposite(color:$color)
        }"""
    )

    variable_values = {
        "color": "RED",
    }

    result = client.execute(query, variable_values=variable_values)

    print(result)

    opposite_color = result["opposite"]

    assert isinstance(opposite_color, Color)
    assert opposite_color == CYAN


def test_opposite_color_variable_serialized_by_gql():

    client = Client(schema=schema, parse_results=True)

    query = gql(
        """
        query GetOppositeColor($color: Color) {
            opposite(color:$color)
        }"""
    )

    variable_values = {
        "color": RED,
    }

    result = client.execute(
        query, variable_values=variable_values, serialize_variables=True
    )

    print(result)

    opposite_color = result["opposite"]

    assert isinstance(opposite_color, Color)
    assert opposite_color == CYAN


def test_list():

    query = gql("{list}")

    client = Client(schema=schema, parse_results=True)

    result = client.execute(query)

    print(result)

    big_list = result["list"]

    assert big_list == list_of_list_of_list[0][0]


def test_list_of_list():

    query = gql("{list_of_list}")

    client = Client(schema=schema, parse_results=True)

    result = client.execute(query)

    print(result)

    big_list = result["list_of_list"]

    assert big_list == list_of_list_of_list[0]


def test_list_of_list_of_list():

    query = gql("{list_of_list_of_list}")

    client = Client(schema=schema, parse_results=True)

    result = client.execute(query)

    print(result)

    big_list = result["list_of_list_of_list"]

    assert big_list == list_of_list_of_list


def test_update_schema_enum():

    assert schema.get_type("Color").parse_value("RED") == Color.RED

    # Using values

    update_schema_enum(schema, "Color", Color, use_enum_values=True)

    assert schema.get_type("Color").parse_value("RED") == 0
    assert schema.get_type("Color").serialize(1) == "GREEN"

    update_schema_enum(schema, "Color", Color)

    assert schema.get_type("Color").parse_value("RED") == Color.RED
    assert schema.get_type("Color").serialize(Color.RED) == "RED"


def test_update_schema_enum_errors():

    with pytest.raises(KeyError) as exc_info:
        update_schema_enum(schema, "Corlo", Color)

    assert "Enum Corlo not found in schema!" in str(exc_info)

    with pytest.raises(TypeError) as exc_info:
        update_schema_enum(schema, "Color", 6)

    assert "Invalid type for enum values: " in str(exc_info)

    with pytest.raises(TypeError) as exc_info:
        update_schema_enum(schema, "RootQueryType", Color)

    assert 'The type "RootQueryType" is not a GraphQLEnumType, it is a' in str(exc_info)

    with pytest.raises(KeyError) as exc_info:
        update_schema_enum(schema, "Color", {"RED": Color.RED})

    assert 'Enum key "GREEN" not found in provided values!' in str(exc_info)


def test_parse_results_with_operation_type():

    client = Client(schema=schema, parse_results=True)

    query = gql(
        """
        query GetAll {
            all
        }
        query GetOppositeColor($color: Color) {
            opposite(color:$color)
        }
        query GetOppositeColor2($color: Color) {
            other_opposite:opposite(color:$color)
        }
        query GetOppositeColor3 {
            opposite(color: YELLOW)
        }
        query GetListOfListOfList {
            list_of_list_of_list
        }
        """
    )

    variable_values = {
        "color": "RED",
    }

    result = client.execute(
        query, variable_values=variable_values, operation_name="GetOppositeColor"
    )

    print(result)

    opposite_color = result["opposite"]

    assert isinstance(opposite_color, Color)
    assert opposite_color == CYAN
