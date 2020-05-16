from graphql import GraphQLArgument, GraphQLField, GraphQLObjectType, GraphQLSchema

from tests.starwars.schema import (
    droidType,
    episodeEnum,
    humanType,
    mutationType,
    queryType,
    reviewInputType,
    reviewType,
)
from tests_py36.fixtures import reviewAdded

subscriptionType = GraphQLObjectType(
    "Subscription",
    fields=lambda: {
        "reviewAdded": GraphQLField(
            reviewType,
            args={
                "episode": GraphQLArgument(
                    description="Episode to review", type_=episodeEnum,  # type: ignore
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
