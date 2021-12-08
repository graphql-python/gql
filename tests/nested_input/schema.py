import json

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInputObjectField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
)

nestedInput = GraphQLInputObjectType(
    "Nested",
    description="The input object that has a field pointing to itself",
    fields={"foo": GraphQLInputObjectField(GraphQLInt, description="foo")},
)

nestedInput.fields["child"] = GraphQLInputObjectField(nestedInput, description="child")

queryType = GraphQLObjectType(
    "Query",
    fields=lambda: {
        "echo": GraphQLField(
            args={"nested": GraphQLArgument(type_=nestedInput)},
            resolver=lambda *args, **kwargs: json.dumps(kwargs["nested"]),
            type_=GraphQLString,
        ),
    },
)

NestedInputSchema = GraphQLSchema(query=queryType, types=[nestedInput],)
