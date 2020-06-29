import asyncio

from graphql import (
    GraphQLArgument,
    GraphQLEnumType,
    GraphQLEnumValue,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInt,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLString,
    get_introspection_query,
    graphql_sync,
    print_schema,
)

from .fixtures import (
    createReview,
    getCharacters,
    getDroid,
    getFriends,
    getHeroAsync,
    getHuman,
    reviews,
)

episodeEnum = GraphQLEnumType(
    "Episode",
    description="One of the films in the Star Wars Trilogy",
    values={
        "NEWHOPE": GraphQLEnumValue(4, description="Released in 1977.",),
        "EMPIRE": GraphQLEnumValue(5, description="Released in 1980.",),
        "JEDI": GraphQLEnumValue(6, description="Released in 1983.",),
    },
)

characterInterface = GraphQLInterfaceType(
    "Character",
    description="A character in the Star Wars Trilogy",
    fields=lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the character."
        ),
        "name": GraphQLField(GraphQLString, description="The name of the character."),
        "friends": GraphQLField(
            GraphQLList(characterInterface),  # type: ignore
            description="The friends of the character,"
            " or an empty list if they have none.",
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episodeEnum), description="Which movies they appear in."
        ),
    },
    resolve_type=lambda character, *_: humanType  # type: ignore
    if getHuman(character.id)
    else droidType,  # type: ignore
)

humanType = GraphQLObjectType(
    "Human",
    description="A humanoid creature in the Star Wars universe.",
    fields=lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the human.",
        ),
        "name": GraphQLField(GraphQLString, description="The name of the human.",),
        "friends": GraphQLField(
            GraphQLList(characterInterface),
            description="The friends of the human, or an empty list if they have none.",
            resolve=lambda human, info, **args: getFriends(human),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episodeEnum), description="Which movies they appear in.",
        ),
        "homePlanet": GraphQLField(
            GraphQLString,
            description="The home planet of the human, or null if unknown.",
        ),
    },
    interfaces=[characterInterface],
)

droidType = GraphQLObjectType(
    "Droid",
    description="A mechanical creature in the Star Wars universe.",
    fields=lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the droid.",
        ),
        "name": GraphQLField(GraphQLString, description="The name of the droid.",),
        "friends": GraphQLField(
            GraphQLList(characterInterface),
            description="The friends of the droid, or an empty list if they have none.",
            resolve=lambda droid, info, **args: getFriends(droid),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episodeEnum), description="Which movies they appear in.",
        ),
        "primaryFunction": GraphQLField(
            GraphQLString, description="The primary function of the droid.",
        ),
    },
    interfaces=[characterInterface],
)

reviewType = GraphQLObjectType(
    "Review",
    description="Represents a review for a movie",
    fields=lambda: {
        "episode": GraphQLField(episodeEnum, description="The movie"),
        "stars": GraphQLField(
            GraphQLNonNull(GraphQLInt),
            description="The number of stars this review gave, 1-5",
        ),
        "commentary": GraphQLField(
            GraphQLString, description="Comment about the movie"
        ),
    },
)

reviewInputType = GraphQLInputObjectType(
    "ReviewInput",
    description="The input object sent when someone is creating a new review",
    fields={
        "stars": GraphQLInputField(GraphQLInt, description="0-5 stars"),
        "commentary": GraphQLInputField(
            GraphQLString, description="Comment about the movie, optional"
        ),
    },
)

queryType = GraphQLObjectType(
    "Query",
    fields=lambda: {
        "hero": GraphQLField(
            characterInterface,
            args={
                "episode": GraphQLArgument(
                    description="If omitted, returns the hero of the whole saga. If "
                    "provided, returns the hero of that particular episode.",
                    type_=episodeEnum,  # type: ignore
                )
            },
            resolve=lambda root, info, **args: getHeroAsync(args.get("episode")),
        ),
        "human": GraphQLField(
            humanType,
            args={
                "id": GraphQLArgument(
                    description="id of the human", type_=GraphQLNonNull(GraphQLString),
                )
            },
            resolve=lambda root, info, **args: getHuman(args["id"]),
        ),
        "droid": GraphQLField(
            droidType,
            args={
                "id": GraphQLArgument(
                    description="id of the droid", type_=GraphQLNonNull(GraphQLString),
                )
            },
            resolve=lambda root, info, **args: getDroid(args["id"]),
        ),
        "characters": GraphQLField(
            GraphQLList(characterInterface),
            args={
                "ids": GraphQLArgument(
                    description="list of character ids",
                    type_=GraphQLList(GraphQLString),
                )
            },
            resolve=lambda root, info, **args: getCharacters(args["ids"]),
        ),
    },
)

mutationType = GraphQLObjectType(
    "Mutation",
    description="The mutation type, represents all updates we can make to our data",
    fields=lambda: {
        "createReview": GraphQLField(
            reviewType,
            args={
                "episode": GraphQLArgument(
                    description="Episode to create review",
                    type_=episodeEnum,  # type: ignore
                ),
                "review": GraphQLArgument(
                    description="set alive status", type_=reviewInputType,
                ),
            },
            resolve=lambda root, info, **args: createReview(
                args.get("episode"), args.get("review")
            ),
        ),
    },
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


StarWarsIntrospection = graphql_sync(StarWarsSchema, get_introspection_query()).data

StarWarsTypeDef = print_schema(StarWarsSchema)
