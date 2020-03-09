import asyncio
from asyncio import get_event_loop

import pytest
from graphql import subscribe
from graphql.error import format_error
from graphql.execution.executors.asyncio import AsyncioExecutor

from gql import Client, gql

from .schema import StarWarsSchema


@pytest.fixture
def client():
    return Client(schema=StarWarsSchema)


def test_hero_name_query(client):
    query = gql('''
        query HeroNameQuery {
          hero {
            name
          }
        }
    ''')
    expected = {
        'hero': {
            'name': 'R2-D2'
        }
    }
    result = client.execute(query)
    assert result == expected


def test_hero_name_and_friends_query(client):
    query = gql('''
        query HeroNameAndFriendsQuery {
          hero {
            id
            name
            friends {
              name
            }
          }
        }
    ''')
    expected = {
        'hero': {
            'id': '2001',
            'name': 'R2-D2',
            'friends': [
                {'name': 'Luke Skywalker'},
                {'name': 'Han Solo'},
                {'name': 'Leia Organa'},
            ]
        }
    }
    result = client.execute(query)
    assert result == expected


def test_nested_query(client):
    query = gql('''
        query NestedQuery {
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
        }
    ''')
    expected = {
        'hero': {
            'name': 'R2-D2',
            'friends': [
                {
                    'name': 'Luke Skywalker',
                    'appearsIn': ['NEWHOPE', 'EMPIRE', 'JEDI'],
                    'friends': [
                        {
                            'name': 'Han Solo',
                        },
                        {
                            'name': 'Leia Organa',
                        },
                        {
                            'name': 'C-3PO',
                        },
                        {
                            'name': 'R2-D2',
                        },
                    ]
                },
                {
                    'name': 'Han Solo',
                    'appearsIn': ['NEWHOPE', 'EMPIRE', 'JEDI'],
                    'friends': [
                        {
                            'name': 'Luke Skywalker',
                        },
                        {
                            'name': 'Leia Organa',
                        },
                        {
                            'name': 'R2-D2',
                        },
                    ]
                },
                {
                    'name': 'Leia Organa',
                    'appearsIn': ['NEWHOPE', 'EMPIRE', 'JEDI'],
                    'friends': [
                        {
                            'name': 'Luke Skywalker',
                        },
                        {
                            'name': 'Han Solo',
                        },
                        {
                            'name': 'C-3PO',
                        },
                        {
                            'name': 'R2-D2',
                        },
                    ]
                },
            ]
        }
    }
    result = client.execute(query)
    assert result == expected


def test_fetch_luke_query(client):
    query = gql('''
        query FetchLukeQuery {
          human(id: "1000") {
            name
          }
        }
    ''')
    expected = {
        'human': {
            'name': 'Luke Skywalker',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_fetch_some_id_query(client):
    query = gql('''
        query FetchSomeIDQuery($someId: String!) {
          human(id: $someId) {
            name
          }
        }
    ''')
    params = {
        'someId': '1000',
    }
    expected = {
        'human': {
            'name': 'Luke Skywalker',
        }
    }
    result = client.execute(query, variable_values=params)
    assert result == expected


def test_fetch_some_id_query2(client):
    query = gql('''
        query FetchSomeIDQuery($someId: String!) {
          human(id: $someId) {
            name
          }
        }
    ''')
    params = {
        'someId': '1002',
    }
    expected = {
        'human': {
            'name': 'Han Solo',
        }
    }
    result = client.execute(query, variable_values=params)
    assert result == expected


def test_invalid_id_query(client):
    query = gql('''
        query humanQuery($id: String!) {
          human(id: $id) {
            name
          }
        }
    ''')
    params = {
        'id': 'not a valid id',
    }
    expected = {
        'human': None
    }
    result = client.execute(query, variable_values=params)
    assert result == expected


def test_fetch_luke_aliased(client):
    query = gql('''
        query FetchLukeAliased {
          luke: human(id: "1000") {
            name
          }
        }
    ''')
    expected = {
        'luke': {
            'name': 'Luke Skywalker',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_fetch_luke_and_leia_aliased(client):
    query = gql('''
        query FetchLukeAndLeiaAliased {
          luke: human(id: "1000") {
            name
          }
          leia: human(id: "1003") {
            name
          }
        }
    ''')
    expected = {
        'luke': {
            'name': 'Luke Skywalker',
        },
        'leia': {
            'name': 'Leia Organa',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_duplicate_fields(client):
    query = gql('''
        query DuplicateFields {
          luke: human(id: "1000") {
            name
            homePlanet
          }
          leia: human(id: "1003") {
            name
            homePlanet
          }
        }
    ''')
    expected = {
        'luke': {
            'name': 'Luke Skywalker',
            'homePlanet': 'Tatooine',
        },
        'leia': {
            'name': 'Leia Organa',
            'homePlanet': 'Alderaan',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_use_fragment(client):
    query = gql('''
        query UseFragment {
          luke: human(id: "1000") {
            ...HumanFragment
          }
          leia: human(id: "1003") {
            ...HumanFragment
          }
        }
        fragment HumanFragment on Human {
          name
          homePlanet
        }
    ''')
    expected = {
        'luke': {
            'name': 'Luke Skywalker',
            'homePlanet': 'Tatooine',
        },
        'leia': {
            'name': 'Leia Organa',
            'homePlanet': 'Alderaan',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_check_type_of_r2(client):
    query = gql('''
        query CheckTypeOfR2 {
          hero {
            __typename
            name
          }
        }
    ''')
    expected = {
        'hero': {
            '__typename': 'Droid',
            'name': 'R2-D2',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_check_type_of_luke(client):
    query = gql('''
        query CheckTypeOfLuke {
          hero(episode: EMPIRE) {
            __typename
            name
          }
        }
    ''')
    expected = {
        'hero': {
            '__typename': 'Human',
            'name': 'Luke Skywalker',
        }
    }
    result = client.execute(query)
    assert result == expected


def test_parse_error(client):
    result = None
    with pytest.raises(Exception) as exc_info:
        query = gql('''
            qeury
        ''')
        result = client.execute(query)
    error = exc_info.value
    formatted_error = format_error(error)
    assert formatted_error['locations'] == [{'column': 13, 'line': 2}]
    assert 'Syntax Error GraphQL request (2:13) Unexpected Name "qeury"' in formatted_error['message']
    assert not result


def test_mutation_result(client):
    query = gql('''
        mutation CreateReviewForEpisode($ep: Episode!, $review: ReviewInput!) {
          createReview(episode: $ep, review: $review) {
            stars
            commentary
          }
        }
    ''')
    params = {
        'ep': 'JEDI',
        'review': {
            'stars': 5,
            'commentary': 'This is a great movie!'
        }
    }
    expected = {
        'createReview': {
            'stars': 5,
            'commentary': 'This is a great movie!'
        }
    }
    result = client.execute(query, variable_values=params)
    assert result == expected


class ObservableAsyncIterable:
    def __init__(self, observable):
        self.disposable = None
        self.queue = asyncio.Queue()
        self.observable = observable

    def __aiter__(self):
        return self

    async def __anext__(self):
        type_, val = await self.queue.get()
        if type_ in ('E', 'C'):
            raise StopAsyncIteration()
        return val

    async def __aenter__(self):
        self.disposable = self.observable.subscribe(
            on_next=lambda val: self.queue.put_nowait(('N', val)),
            on_error=lambda exc: self.queue.put_nowait(('E', exc)),
            on_completed=lambda: self.queue.put_nowait(('C', None)),
        )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.disposable.dispose()


@pytest.mark.asyncio
async def test_subscription_support():
    subs = gql('''
        subscription ListenEpisodeReviews($ep: Episode!) {
          reviewAdded(episode: $ep) {
            stars,
            commentary,
            episode
          }
        }
    ''')
    params = {
        'ep': 'JEDI'
    }
    expected_one = {
        'stars': 3,
        'commentary': 'Was expecting more stuff',
        'episode': 'JEDI'
    }
    expected_two = {
        'stars': 5,
        'commentary': 'This is a great movie!',
        'episode': 'JEDI'
    }
    # For asyncio, requires set return_promise=True as stated on the following comment
    # https://github.com/graphql-python/graphql-core/issues/63#issuecomment-568270864
    loop = get_event_loop()
    execution_result = await subscribe(
        schema=StarWarsSchema,
        document_ast=subs,
        return_promise=True,
        variable_values=params,
        executor=AsyncioExecutor(loop=loop)
    )
    expected = []
    async with ObservableAsyncIterable(execution_result) as oai:
        async for i in oai:
            review = i.to_dict()
            expected.append(review['data']['reviewAdded'])
    assert expected[0] == expected_one
    assert expected[1] == expected_two
