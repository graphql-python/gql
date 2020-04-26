from graphql import (
    graphql,
    print_schema,
    GraphQLField,
    GraphQLArgument,
    GraphQLObjectType,
    GraphQLSchema,
)
from graphql.utils.introspection_query import introspection_query

from tests.starwars.schema import (
    reviewType,
    episodeEnum,
    queryType,
    mutationType,
    humanType,
    droidType,
    reviewInputType,
)
from tests_py36.fixtures import reviewAdded

subscriptionType = GraphQLObjectType(
    "Subscription",
    fields=lambda: {
        "reviewAdded": GraphQLField(
            reviewType,
            args={
                "episode": GraphQLArgument(
                    description="Episode to review", type=episodeEnum,
                )
            },
            resolver=lambda root, info, **args: reviewAdded(args.get("episode")),
        )
    },
)

StarWarsSchema = GraphQLSchema(
    query=queryType,
    mutation=mutationType,
    subscription=subscriptionType,
    types=[humanType, droidType, reviewType, reviewInputType],
)

StarWarsIntrospection = graphql(StarWarsSchema, introspection_query).data  # type: ignore

StarWarsTypeDef = print_schema(StarWarsSchema)
