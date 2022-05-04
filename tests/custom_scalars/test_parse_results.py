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

static_result = {
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


def resolve_test(root, _info, count):
    return static_result


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
            resolve=resolve_test,
        ),
    },
)

schema = GraphQLSchema(query=queryType)


def test_parse_results_null_mapping():
    """This is a regression test for the issue:
    https://github.com/graphql-python/gql/issues/325

    Most of the parse_results tests are in tests/starwars/test_parse_results.py
    """

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
        "test": static_result
    }
