import asyncio
from typing import cast

from graphql import (
    DirectiveLocation,
    GraphQLArgument,
    GraphQLDirective,
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
    IntrospectionQuery,
    get_introspection_query,
    graphql_sync,
    print_schema,
    specified_directives,
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
        "NEWHOPE": GraphQLEnumValue(
            4,
            description="Released in 1977.",
        ),
        "EMPIRE": GraphQLEnumValue(
            5,
            description="Released in 1980.",
        ),
        "JEDI": GraphQLEnumValue(
            6,
            description="Released in 1983.",
        ),
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
            GraphQLNonNull(GraphQLString),
            description="The id of the human.",
        ),
        "name": GraphQLField(
            GraphQLString,
            description="The name of the human.",
        ),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the human, or an empty list if they have none.",
            resolve=lambda human, _info: get_friends(human),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum),
            description="Which movies they appear in.",
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
            GraphQLNonNull(GraphQLString),
            description="The id of the droid.",
        ),
        "name": GraphQLField(
            GraphQLString,
            description="The name of the droid.",
        ),
        "friends": GraphQLField(
            GraphQLList(character_interface),
            description="The friends of the droid, or an empty list if they have none.",
            resolve=lambda droid, _info: get_friends(droid),
        ),
        "appearsIn": GraphQLField(
            GraphQLList(episode_enum),
            description="Which movies they appear in.",
        ),
        "primaryFunction": GraphQLField(
            GraphQLString,
            description="The primary function of the droid.",
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
        "deprecated_input_field": GraphQLInputField(
            GraphQLString,
            description="deprecated field example",
            deprecation_reason="deprecated for testing",
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
            resolve=lambda _source, _info, episode=None: get_hero_async(episode),
        ),
        "human": GraphQLField(
            human_type,
            args={
                "id": GraphQLArgument(
                    description="id of the human",
                    type_=GraphQLNonNull(GraphQLString),
                )
            },
            resolve=lambda _source, _info, id: get_human(id),
        ),
        "droid": GraphQLField(
            droid_type,
            args={
                "id": GraphQLArgument(
                    description="id of the droid",
                    type_=GraphQLNonNull(GraphQLString),
                )
            },
            resolve=lambda _source, _info, id: get_droid(id),
        ),
        "characters": GraphQLField(
            GraphQLList(character_interface),
            args={
                "ids": GraphQLArgument(
                    GraphQLList(GraphQLString),
                    description="list of character ids",
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
                    episode_enum,
                    description="Episode to create review",
                ),
                "review": GraphQLArgument(
                    description="set alive status",
                    type_=review_input_type,
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
                    episode_enum,
                    description="Episode to review",
                )
            },
            subscribe=subscribe_reviews,
            resolve=resolve_review,
        )
    },
)

query_directive = GraphQLDirective(
    name="query",
    description="Test directive for QUERY location",
    locations=[DirectiveLocation.QUERY],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

field_directive = GraphQLDirective(
    name="field",
    description="Test directive for FIELD location",
    locations=[DirectiveLocation.FIELD],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

fragment_spread_directive = GraphQLDirective(
    name="fragmentSpread",
    description="Test directive for FRAGMENT_SPREAD location",
    locations=[DirectiveLocation.FRAGMENT_SPREAD],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

inline_fragment_directive = GraphQLDirective(
    name="inlineFragment",
    description="Test directive for INLINE_FRAGMENT location",
    locations=[DirectiveLocation.INLINE_FRAGMENT],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

fragment_definition_directive = GraphQLDirective(
    name="fragmentDefinition",
    description="Test directive for FRAGMENT_DEFINITION location",
    locations=[DirectiveLocation.FRAGMENT_DEFINITION],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

mutation_directive = GraphQLDirective(
    name="mutation",
    description="Test directive for MUTATION location (tests keyword conflict)",
    locations=[DirectiveLocation.MUTATION],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

subscription_directive = GraphQLDirective(
    name="subscription",
    description="Test directive for SUBSCRIPTION location",
    locations=[DirectiveLocation.SUBSCRIPTION],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

variable_definition_directive = GraphQLDirective(
    name="variableDefinition",
    description="Test directive for VARIABLE_DEFINITION location",
    locations=[DirectiveLocation.VARIABLE_DEFINITION],
    args={
        "value": GraphQLArgument(
            GraphQLString, description="A string value for the variable"
        )
    },
)

repeat_directive = GraphQLDirective(
    name="repeat",
    description="Test repeatable directive for FIELD location",
    locations=[DirectiveLocation.FIELD],
    args={
        "value": GraphQLArgument(
            GraphQLString,
            description="A string value for the repeatable directive",
        )
    },
    is_repeatable=True,
)


StarWarsSchema = GraphQLSchema(
    query=query_type,
    mutation=mutation_type,
    subscription=subscription_type,
    types=[human_type, droid_type, review_type, review_input_type],
    directives=[
        *specified_directives,
        query_directive,
        field_directive,
        fragment_spread_directive,
        inline_fragment_directive,
        fragment_definition_directive,
        mutation_directive,
        subscription_directive,
        variable_definition_directive,
        repeat_directive,
    ],
)


StarWarsIntrospection = cast(
    IntrospectionQuery, graphql_sync(StarWarsSchema, get_introspection_query()).data
)

StarWarsTypeDef = print_schema(StarWarsSchema)
