from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLObjectType,
    GraphQLSchema,
)

nestedInput = GraphQLInputObjectType(
    "Nested",
    description="The input object that has a field pointing to itself",
    fields={"foo": GraphQLInputField(GraphQLInt, description="foo")},
)

nestedInput.fields["child"] = GraphQLInputField(nestedInput, description="child")

queryType = GraphQLObjectType(
    "Query",
    fields=lambda: {
        "foo": GraphQLField(
            args={"nested": GraphQLArgument(type_=nestedInput)},
            resolve=lambda *args, **kwargs: 1,
            type_=GraphQLInt,
        ),
    },
)

NestedInputSchema = GraphQLSchema(query=queryType, types=[nestedInput],)
