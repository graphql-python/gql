from .schema import queryType, characterInterface, humanType
from gql import dsl


# We construct a Simple DSL objects for easy field referencing

class Query(object):
  hero = queryType.get_fields()['hero']
  human = queryType.get_fields()['human']


class Character(object):
  id = characterInterface.get_fields()['id']
  name = characterInterface.get_fields()['name']
  friends = characterInterface.get_fields()['friends']
  appears_in = characterInterface.get_fields()['appearsIn']


class Human(object):
  name = humanType.get_fields()['name']


def test_hero_name_query():
    query = '''
hero {
  name
}
    '''.strip()
    query_dsl = dsl.field(Query.hero).get(
        Character.name
    )
    assert query == str(query_dsl)


def test_hero_name_and_friends_query():
    query = '''
hero {
  id
  name
  friends {
    name
  }
}
    '''.strip()
    query_dsl = dsl.field(Query.hero).get(
        Character.id,
        Character.name,
        dsl.field(Character.friends).get(
            Character.name,
        )
    )
    assert query == str(query_dsl)


def test_nested_query():
    query = '''
hero {
  name
  friends {
    name
    appearsIn
    friends {
      name
    }
  }
}
    '''.strip()
    query_dsl = dsl.field(Query.hero).get(
        Character.name,
        dsl.field(Character.friends).get(
            Character.name,
            Character.appears_in,
            dsl.field(Character.friends).get(
                Character.name
            )
        )
    )
    assert query == str(query_dsl)


def test_fetch_luke_query():
    query = '''
human(id: "1000") {
  name
}
    '''.strip()
    query_dsl = dsl.field(Query.human, id="1000").get(
      Human.name,
    )

    assert query == str(query_dsl)


# def test_fetch_some_id_query():
#     query = '''
#         query FetchSomeIDQuery($someId: String!) {
#           human(id: $someId) {
#             name
#           }
#         }
#     '''
#     params = {
#         'someId': '1000',
#     }
#     expected = {
#         'human': {
#             'name': 'Luke Skywalker',
#         }
#     }
#     result = schema.execute(query, None, params)
#     assert not result.errors
#     assert result.data == expected


# def test_fetch_some_id_query2():
#     query = '''
#         query FetchSomeIDQuery($someId: String!) {
#           human(id: $someId) {
#             name
#           }
#         }
#     '''
#     params = {
#         'someId': '1002',
#     }
#     expected = {
#         'human': {
#             'name': 'Han Solo',
#         }
#     }
#     result = schema.execute(query, None, params)
#     assert not result.errors
#     assert result.data == expected


# def test_invalid_id_query():
#     query = '''
#         query humanQuery($id: String!) {
#           human(id: $id) {
#             name
#           }
#         }
#     '''
#     params = {
#         'id': 'not a valid id',
#     }
#     expected = {
#         'human': None
#     }
#     result = schema.execute(query, None, params)
#     assert not result.errors
#     assert result.data == expected


def test_fetch_luke_aliased():
    query = '''
luke: human(id: "1000") {
  name
}
    '''.strip()
    expected = {
        'luke': {
            'name': 'Luke Skywalker',
        }
    }
    query_dsl = dsl.field(Query.human, id=1000).alias('luke').get(
        Character.name,
    )
    assert query == str(query_dsl)


# def test_fetch_luke_and_leia_aliased():
#     query = '''
#         query FetchLukeAndLeiaAliased {
#           luke: human(id: "1000") {
#             name
#           }
#           leia: human(id: "1003") {
#             name
#           }
#         }
#     '''
#     expected = {
#         'luke': {
#             'name': 'Luke Skywalker',
#         },
#         'leia': {
#             'name': 'Leia Organa',
#         }
#     }
#     result = schema.execute(query)
#     assert not result.errors
#     assert result.data == expected


# def test_duplicate_fields():
#     query = '''
#         query DuplicateFields {
#           luke: human(id: "1000") {
#             name
#             homePlanet
#           }
#           leia: human(id: "1003") {
#             name
#             homePlanet
#           }
#         }
#     '''
#     expected = {
#         'luke': {
#             'name': 'Luke Skywalker',
#             'homePlanet': 'Tatooine',
#         },
#         'leia': {
#             'name': 'Leia Organa',
#             'homePlanet': 'Alderaan',
#         }
#     }
#     result = schema.execute(query)
#     assert not result.errors
#     assert result.data == expected


# def test_use_fragment():
#     query = '''
#         query UseFragment {
#           luke: human(id: "1000") {
#             ...HumanFragment
#           }
#           leia: human(id: "1003") {
#             ...HumanFragment
#           }
#         }
#         fragment HumanFragment on Human {
#           name
#           homePlanet
#         }
#     '''
#     expected = {
#         'luke': {
#             'name': 'Luke Skywalker',
#             'homePlanet': 'Tatooine',
#         },
#         'leia': {
#             'name': 'Leia Organa',
#             'homePlanet': 'Alderaan',
#         }
#     }
#     result = schema.execute(query)
#     assert not result.errors
#     assert result.data == expected


# def test_check_type_of_r2():
#     query = '''
#         query CheckTypeOfR2 {
#           hero {
#             __typename
#             name
#           }
#         }
#     '''
#     expected = {
#         'hero': {
#             '__typename': 'Droid',
#             'name': 'R2-D2',
#         }
#     }
#     result = schema.execute(query)
#     assert not result.errors
#     assert result.data == expected


# def test_check_type_of_luke():
#     query = '''
#         query CheckTypeOfLuke {
#           hero(episode: EMPIRE) {
#             __typename
#             name
#           }
#         }
#     '''
#     expected = {
#         'hero': {
#             '__typename': 'Human',
#             'name': 'Luke Skywalker',
#         }
#     }
#     result = schema.execute(query)
#     assert not result.errors
#     assert result.data == expected
