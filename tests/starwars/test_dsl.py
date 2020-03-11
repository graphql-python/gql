import pytest

from gql import Client
from gql.dsl import DSLSchema

from .schema import StarWarsSchema


@pytest.fixture
def ds():
    client = Client(schema=StarWarsSchema)
    ds = DSLSchema(client)
    return ds


def test_invalid_field_on_type_query(ds):
    with pytest.raises(KeyError) as exc_info:
        ds.Query.extras.select(
            ds.Character.name
        )
    assert "Field extras does not exist in type Query." in str(exc_info.value)


def test_incompatible_query_field(ds):
    with pytest.raises(Exception) as exc_info:
        ds.query('hero')
    assert "Received incompatible query field" in str(exc_info.value)


def test_hero_name_query(ds):
    query = '''
hero {
  name
}
    '''.strip()
    query_dsl = ds.Query.hero.select(
        ds.Character.name
    )
    assert query == str(query_dsl)


def test_hero_name_and_friends_query(ds):
    query = '''
hero {
  id
  name
  friends {
    name
  }
}
    '''.strip()
    query_dsl = ds.Query.hero.select(
        ds.Character.id,
        ds.Character.name,
        ds.Character.friends.select(
            ds.Character.name,
        )
    )
    assert query == str(query_dsl)


def test_nested_query(ds):
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
    query_dsl = ds.Query.hero.select(
        ds.Character.name,
        ds.Character.friends.select(
            ds.Character.name,
            ds.Character.appears_in,
            ds.Character.friends.select(
                ds.Character.name
            )
        )
    )
    assert query == str(query_dsl)


def test_fetch_luke_query(ds):
    query = '''
human(id: "1000") {
  name
}
    '''.strip()
    query_dsl = ds.Query.human(id="1000").select(
        ds.Human.name,
    )

    assert query == str(query_dsl)


def test_fetch_luke_aliased(ds):
    query = '''
luke: human(id: "1000") {
  name
}
    '''.strip()
    query_dsl = ds.Query.human.args(id=1000).alias('luke').select(
        ds.Character.name,
    )
    assert query == str(query_dsl)


def test_hero_name_query_result(ds):
    result = ds.query(
        ds.Query.hero.select(
            ds.Character.name
        )
    )
    expected = {
        'hero': {
            'name': 'R2-D2'
        }
    }
    assert result == expected


def test_arg_serializer_list(ds):
    result = ds.query(
        ds.Query.characters.args(ids=[1000, 1001, 1003]).select(
            ds.Character.name,
        )
    )
    expected = {
        'characters': [
            {
                'name': 'Luke Skywalker'
            },
            {
                'name': 'Darth Vader'
            },
            {
                'name': 'Leia Organa'
            }
        ]
    }
    assert result == expected


def test_arg_serializer_enum(ds):
    result = ds.query(
        ds.Query.hero.args(episode=5).select(
            ds.Character.name
        )
    )
    expected = {
        'hero': {
            'name': 'Luke Skywalker'
        }
    }
    assert result == expected


def test_human_alive_mutation_result(ds):
    result = ds.mutate(
        ds.Mutation.updateHumanAliveStatus.args(id=1004, status=True).select(
            ds.Human.name,
            ds.Human.isAlive
        )
    )
    expected = {
        'updateHumanAliveStatus': {
            'name': 'Wilhuff Tarkin',
            'isAlive': True
        }
    }
    assert result == expected
