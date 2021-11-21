from typing import Any, Dict, Optional

import pytest
from graphql import (
    GraphQLArgument,
    GraphQLError,
    GraphQLField,
    GraphQLFloat,
    GraphQLInt,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.language import ValueNode
from graphql.utilities import value_from_ast_untyped

from gql import Client, gql
from gql.dsl import DSLSchema

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp


def serialize_json(value: Any) -> Dict[str, Any]:
    return value


def parse_json_value(value: Any) -> Any:
    return value


def parse_json_literal(
    value_node: ValueNode, variables: Optional[Dict[str, Any]] = None
) -> Any:
    return value_from_ast_untyped(value_node, variables)


JsonScalar = GraphQLScalarType(
    name="JSON",
    serialize=serialize_json,
    parse_value=parse_json_value,
    parse_literal=parse_json_literal,
)

root_value = {
    "players": [
        {
            "name": "John",
            "level": 3,
            "is_connected": True,
            "score": 123.45,
            "friends": ["Alex", "Alicia"],
        },
        {
            "name": "Alex",
            "level": 4,
            "is_connected": False,
            "score": 1337.69,
            "friends": None,
        },
    ]
}


def resolve_players(root, _info):
    return root["players"]


queryType = GraphQLObjectType(
    name="Query", fields={"players": GraphQLField(JsonScalar, resolve=resolve_players)},
)


def resolve_add_player(root, _info, player):
    print(f"player = {player!r}")
    root["players"].append(player)
    return {"players": root["players"]}


mutationType = GraphQLObjectType(
    name="Mutation",
    fields={
        "addPlayer": GraphQLField(
            JsonScalar,
            args={"player": GraphQLArgument(GraphQLNonNull(JsonScalar))},
            resolve=resolve_add_player,
        )
    },
)

schema = GraphQLSchema(query=queryType, mutation=mutationType)


def test_json_value_output():

    client = Client(schema=schema, parse_results=True)

    query = gql("query {players}")

    result = client.execute(query, root_value=root_value)

    print(result)

    assert result["players"] == serialize_json(root_value["players"])


def test_json_value_input_in_ast():

    client = Client(schema=schema)

    query = gql(
        """
    mutation adding_player {
        addPlayer(player:  {
          name: "Tom",
          level: 1,
          is_connected: True,
          score: 0,
          friends: [
              "John"
          ]
        })
}"""
    )

    result = client.execute(query, root_value=root_value)

    print(result)

    players = result["addPlayer"]["players"]

    assert players == serialize_json(root_value["players"])
    assert players[-1]["name"] == "Tom"


def test_json_value_input_in_ast_with_variables():

    print(f"{schema.type_map!r}")
    client = Client(schema=schema)

    # Note: we need to manually add the built-in types which
    # are not present in the schema
    schema.type_map["Int"] = GraphQLInt
    schema.type_map["Float"] = GraphQLFloat

    query = gql(
        """
    mutation adding_player(
        $name: String!,
        $level: Int!,
        $is_connected: Boolean,
        $score: Float!,
        $friends: [String!]!) {

        addPlayer(player:  {
          name: $name,
          level: $level,
          is_connected: $is_connected,
          score: $score,
          friends: $friends,
        })
}"""
    )

    variable_values = {
        "name": "Barbara",
        "level": 1,
        "is_connected": False,
        "score": 69,
        "friends": ["Alex", "John"],
    }

    result = client.execute(
        query, variable_values=variable_values, root_value=root_value
    )

    print(result)

    players = result["addPlayer"]["players"]

    assert players == serialize_json(root_value["players"])
    assert players[-1]["name"] == "Barbara"


def test_json_value_input_in_dsl_argument():

    ds = DSLSchema(schema)

    new_player = {
        "name": "Tim",
        "level": 0,
        "is_connected": False,
        "score": 5,
        "friends": ["Lea"],
    }

    query = ds.Mutation.addPlayer(player=new_player)

    print(str(query))

    assert (
        str(query)
        == """addPlayer(
  player: {name: "Tim", level: 0, is_connected: false, score: 5, friends: ["Lea"]}
)"""
    )


def test_none_json_value_input_in_dsl_argument():

    ds = DSLSchema(schema)

    with pytest.raises(GraphQLError) as exc_info:
        ds.Mutation.addPlayer(player=None)

    assert "Received Null value for a Non-Null type JSON." in str(exc_info.value)


def test_json_value_input_with_none_list_in_dsl_argument():

    ds = DSLSchema(schema)

    new_player = {
        "name": "Bob",
        "level": 9001,
        "is_connected": True,
        "score": 666.66,
        "friends": None,
    }

    query = ds.Mutation.addPlayer(player=new_player)

    print(str(query))

    assert (
        str(query)
        == """addPlayer(
  player: {name: "Bob", level: 9001, is_connected: true, score: 666.66, friends: null}
)"""
    )
