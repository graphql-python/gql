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
    create_review,
    get_characters,
    get_droid,
    get_friends,
    get_hero_async,
    get_human,
    reviews,
)

episode_enum = GraphQLEnumType(
    "Episode",
    {
        "NEWHOPE": GraphQLEnumValue(4, description="Released in 1977.",),
        "EMPIRE": GraphQLEnumValue(5, description="Released in 1980.",),
        "JEDI": GraphQLEnumValue(6, description="Released in 1983.",),
    },
    description="One of the films in the Star Wars Trilogy",
)


human_type: GraphQLObjectType
droid_type: GraphQLObjectType

character_interface = GraphQLInterfaceType(
    "Character",
    lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the character."
        ),
        "name": GraphQLField(GraphQLString, description="The name of the character."),
        "friends": GraphQLField(
            GraphQLList(character_interface),  # type: ignore
            description="The friends of the character,"
            " or an empty list if they have none.",
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum), description="Which movies they appear in."
        ),
    },
    resolve_type=lambda character, _info, _type: {
        "Human": human_type.name,
        "Droid": droid_type.name,
    }[character.type],
    description="A character in the Star Wars Trilogy",
)

human_type = GraphQLObjectType(
    "Human",
    lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the human.",
        ),
        "name": GraphQLField(GraphQLString, description="The name of the human.",),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the human, or an empty list if they have none.",
            resolve=lambda human, _info: get_friends(human),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum), description="Which movies they appear in.",
        ),
        "homePlanet": GraphQLField(
            GraphQLString,
            description="The home planet of the human, or null if unknown.",
        ),
    },
    interfaces=[character_interface],
    description="A humanoid creature in the Star Wars universe.",
)

droid_type = GraphQLObjectType(
    "Droid",
    lambda: {
        "id": GraphQLField(
            GraphQLNonNull(GraphQLString), description="The id of the droid.",
        ),
        "name": GraphQLField(GraphQLString, description="The name of the droid.",),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the droid, or an empty list if they have none.",
            resolve=lambda droid, _info: get_friends(droid),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum), description="Which movies they appear in.",
        ),
        "primaryFunction": GraphQLField(
            GraphQLString, description="The primary function of the droid.",
        ),
    },
    interfaces=[character_interface],
    description="A mechanical creature in the Star Wars universe.",
)

review_type = GraphQLObjectType(
    "Review",
    lambda: {
        "episode": GraphQLField(episode_enum, description="The movie"),
        "stars": GraphQLField(
            GraphQLNonNull(GraphQLInt),
            description="The number of stars this review gave, 1-5",
        ),
        "commentary": GraphQLField(
            GraphQLString, description="Comment about the movie"
        ),
    },
    description="Represents a review for a movie",
)

review_input_type = GraphQLInputObjectType(
    "ReviewInput",
    lambda: {
        "stars": GraphQLInputField(GraphQLInt, description="0-5 stars"),
        "commentary": GraphQLInputField(
            GraphQLString, description="Comment about the movie, optional"
        ),
    },
    description="The input object sent when someone is creating a new review",
)

query_type = GraphQLObjectType(
    "Query",
    lambda: {
        "hero": GraphQLField(
            character_interface,
            args={
                "episode": GraphQLArgument(
                    episode_enum,
                    description="If omitted, returns the hero of the whole saga. If "
                    "provided, returns the hero of that particular episode.",
                )
            },
            resolve=lambda _souce, _info, episode=None: get_hero_async(episode),
        ),
        "human": GraphQLField(
            human_type,
            args={
                "id": GraphQLArgument(
                    description="id of the human", type_=GraphQLNonNull(GraphQLString),
                )
            },
            resolve=lambda _souce, _info, id: get_human(id),
        ),
        "droid": GraphQLField(
            droid_type,
            args={
                "id": GraphQLArgument(
                    description="id of the droid", type_=GraphQLNonNull(GraphQLString),
                )
            },
            resolve=lambda _source, _info, id: get_droid(id),
        ),
        "characters": GraphQLField(
            GraphQLList(character_interface),
            args={
                "ids": GraphQLArgument(
                    GraphQLList(GraphQLString), description="list of character ids",
                )
            },
            resolve=lambda _source, _info, ids=None: get_characters(ids),
        ),
    },
)

mutation_type = GraphQLObjectType(
    "Mutation",
    lambda: {
        "createReview": GraphQLField(
            review_type,
            args={
                "episode": GraphQLArgument(
                    episode_enum, description="Episode to create review",
                ),
                "review": GraphQLArgument(
                    description="set alive status", type_=review_input_type,
                ),
            },
            resolve=lambda _source, _info, episode=None, review=None: create_review(
                episode, review
            ),
        ),
    },
    description="The mutation type, represents all updates we can make to our data",
)


async def subscribe_reviews(_root, _info, episode):
    for review in reviews[episode]:
        yield review
        await asyncio.sleep(0.1)


async def resolve_review(review, _info, **_args):
    return review


subscription_type = GraphQLObjectType(
    "Subscription",
    lambda: {
        "reviewAdded": GraphQLField(
            review_type,
            args={
                "episode": GraphQLArgument(
                    episode_enum, description="Episode to review",
                )
            },
            subscribe=subscribe_reviews,
            resolve=resolve_review,
        )
    },
)


StarWarsSchema = GraphQLSchema(
    query=query_type,
    mutation=mutation_type,
    subscription=subscription_type,
    types=[human_type, droid_type, review_type, review_input_type],
)


StarWarsIntrospection = graphql_sync(StarWarsSchema, get_introspection_query()).data

StarWarsTypeDef = print_schema(StarWarsSchema)
