from graphql.type import (GraphQLArgument, GraphQLEnumType, GraphQLEnumValue,
                          GraphQLField, GraphQLInterfaceType, GraphQLList,
                          GraphQLNonNull, GraphQLObjectType, GraphQLSchema,
                          GraphQLString, GraphQLBoolean)

from .fixtures import getCharacters, getDroid, getFriends, getHero, getHuman, updateHumanAlive

episodeEnum = GraphQLEnumType(
    'Episode',
    description='One of the films in the Star Wars Trilogy',
    values={
        'NEWHOPE': GraphQLEnumValue(
            4,
            description='Released in 1977.',
        ),
        'EMPIRE': GraphQLEnumValue(
            5,
            description='Released in 1980.',
        ),
        'JEDI': GraphQLEnumValue(
            6,
            description='Released in 1983.',
        )
    }
)

characterInterface = GraphQLInterfaceType(
    'Character',
    description='A character in the Star Wars Trilogy',
    fields=lambda: {
        'id': GraphQLField(
            GraphQLNonNull(GraphQLString),
            description='The id of the character.'
        ),
        'name': GraphQLField(
            GraphQLString,
            description='The name of the character.'
        ),
        'friends': GraphQLField(
            GraphQLList(characterInterface),
            description='The friends of the character, or an empty list if they have none.'
        ),
        'appearsIn': GraphQLField(
            GraphQLList(episodeEnum),
            description='Which movies they appear in.'
        ),
    },
    resolve_type=lambda character, *_: humanType if getHuman(character.id) else droidType,
)

humanType = GraphQLObjectType(
    'Human',
    description='A humanoid creature in the Star Wars universe.',
    fields=lambda: {
        'id': GraphQLField(
            GraphQLNonNull(GraphQLString),
            description='The id of the human.',
        ),
        'name': GraphQLField(
            GraphQLString,
            description='The name of the human.',
        ),
        'friends': GraphQLField(
            GraphQLList(characterInterface),
            description='The friends of the human, or an empty list if they have none.',
            resolver=lambda human, info, **args: getFriends(human),
        ),
        'appearsIn': GraphQLField(
            GraphQLList(episodeEnum),
            description='Which movies they appear in.',
        ),
        'homePlanet': GraphQLField(
            GraphQLString,
            description='The home planet of the human, or null if unknown.',
        ),
        'isAlive': GraphQLField(
            GraphQLBoolean,
            description='The human is still alive.'
        ),
    },
    interfaces=[characterInterface]
)

droidType = GraphQLObjectType(
    'Droid',
    description='A mechanical creature in the Star Wars universe.',
    fields=lambda: {
        'id': GraphQLField(
            GraphQLNonNull(GraphQLString),
            description='The id of the droid.',
        ),
        'name': GraphQLField(
            GraphQLString,
            description='The name of the droid.',
        ),
        'friends': GraphQLField(
            GraphQLList(characterInterface),
            description='The friends of the droid, or an empty list if they have none.',
            resolver=lambda droid, info, **args: getFriends(droid),
        ),
        'appearsIn': GraphQLField(
            GraphQLList(episodeEnum),
            description='Which movies they appear in.',
        ),
        'primaryFunction': GraphQLField(
            GraphQLString,
            description='The primary function of the droid.',
        )
    },
    interfaces=[characterInterface]
)

queryType = GraphQLObjectType(
    'Query',
    fields=lambda: {
        'hero': GraphQLField(
            characterInterface,
            args={
                'episode': GraphQLArgument(
                    description='If omitted, returns the hero of the whole saga. If '
                                'provided, returns the hero of that particular episode.',
                    type=episodeEnum,
                )
            },
            resolver=lambda root, info, **args: getHero(args.get('episode')),
        ),
        'human': GraphQLField(
            humanType,
            args={
                'id': GraphQLArgument(
                    description='id of the human',
                    type=GraphQLNonNull(GraphQLString),
                )
            },
            resolver=lambda root, info, **args: getHuman(args['id']),
        ),
        'droid': GraphQLField(
            droidType,
            args={
                'id': GraphQLArgument(
                    description='id of the droid',
                    type=GraphQLNonNull(GraphQLString),
                )
            },
            resolver=lambda root, info, **args: getDroid(args['id']),
        ),
        'characters': GraphQLField(
            GraphQLList(characterInterface),
            args={
                'ids': GraphQLArgument(
                    description='list of character ids',
                    type=GraphQLList(GraphQLString),
                )
            },
            resolver=lambda root, info, **args: getCharacters(args['ids']),
        ),
    }
)

mutationType = GraphQLObjectType(
    'Mutation',
    fields=lambda: {
        'updateHumanAliveStatus': GraphQLField(
            humanType,
            args={
                'id': GraphQLArgument(
                    description='id of the human',
                    type=GraphQLNonNull(GraphQLString),
                ),
                'status': GraphQLArgument(
                    description='set alive status',
                    type=GraphQLNonNull(GraphQLBoolean),
                ),
            },
            resolver=lambda root, info, **args: updateHumanAlive(args['id'], args['status']),
        ),
    }
)

StarWarsSchema = GraphQLSchema(query=queryType, mutation=mutationType, types=[humanType, droidType])
