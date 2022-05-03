from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

from gql import Client, gql


def static_result(root, _info, count):
    return {
        "edges": [
            {
                "node": {
                    "from": {"address": "0x45b9ad45995577fe"},
                    "to": {"address": "0x6394e988297f5ed2"},
                }
            },
            {"node": {"from": None, "to": {"address": "0x6394e988297f5ed2"}}},
        ]
    }


Account = GraphQLObjectType(
    name="Account",
    fields={"address": GraphQLField(GraphQLNonNull(GraphQLString))},
)


queryType = GraphQLObjectType(
    name="RootQueryType",
    fields={
        "test": GraphQLField(
            GraphQLObjectType(
                name="test",
                fields={
                    "edges": GraphQLField(
                        GraphQLList(
                            GraphQLObjectType(
                                "example",
                                fields={
                                    "node": GraphQLField(
                                        GraphQLObjectType(
                                            name="node",
                                            fields={
                                                "from": GraphQLField(Account),
                                                "to": GraphQLField(Account),
                                            },
                                        )
                                    )
                                },
                            )
                        )
                    )
                },
            ),
            args={"count": GraphQLArgument(GraphQLInt)},
            resolve=static_result,
        ),
    },
)

schema = GraphQLSchema(query=queryType)


def test_null_mapping():

    client = Client(schema=schema, parse_results=True)
    query = gql(
        """query testQ($count: Int) {test(count: $count){
        edges {
          node {
            from {
                address
            }
            to {
                address
            }
          }
        }
    } }"""
    )

    assert client.execute(query, variable_values={"count": 2}) == {
        "test": {
            "edges": [
                {
                    "node": {
                        "from": {"address": "0x45b9ad45995577fe"},
                        "to": {"address": "0x6394e988297f5ed2"},
                    }
                },
                {"node": {"from": None, "to": {"address": "0x6394e988297f5ed2"}}},
            ]
        }
    }
