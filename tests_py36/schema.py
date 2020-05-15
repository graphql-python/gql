import asyncio

from graphql import (
    GraphQLArgument,
    GraphQLField,
    GraphQLObjectType,
    GraphQLSchema,
    get_introspection_query,
    graphql_sync,
    print_schema,
)

from tests.starwars.fixtures import reviews
from tests.starwars.schema import (
    droidType,
    episodeEnum,
    humanType,
    mutationType,
    queryType,
    reviewInputType,
    reviewType,
)


async def subscribe_reviews(_root, _info, episode):
    for review in reviews[episode]:
        yield review
        await asyncio.sleep(0.1)


async def resolve_review(review, _info, **_args):
    return review


subscriptionType = GraphQLObjectType(
    "Subscription",
    fields=lambda: {
        "reviewAdded": GraphQLField(
            reviewType,
            args={
                "episode": GraphQLArgument(
                    description="Episode to review", type_=episodeEnum,
                )
            },
            subscribe=subscribe_reviews,
            resolve=resolve_review,
        )
    },
)

StarWarsSchema = GraphQLSchema(
    query=queryType,
    mutation=mutationType,
    subscription=subscriptionType,
    types=[humanType, droidType, reviewType, reviewInputType],
)

StarWarsIntrospection = graphql_sync(StarWarsSchema, get_introspection_query()).data  # type: ignore

StarWarsTypeDef = print_schema(StarWarsSchema)
