import pytest
from graphql import GraphQLError

from gql import Client, gql
from tests.starwars.schema import StarWarsSchema


@pytest.fixture
def client():
    return Client(schema=StarWarsSchema)


def test_hero_name_query(client):
    query = gql(
        """
        query HeroNameQuery {
          hero {
            name
          }
        }
        """
    )
    expected = {"hero": {"name": "R2-D2"}}
    result = client.execute(query)
    assert result == expected


def test_hero_name_and_friends_query(client):
    query = gql(
        """
        query HeroNameAndFriendsQuery {
          hero {
            id
            name
            friends {
              name
            }
          }
        }
        """
    )
    expected = {
        "hero": {
            "id": "2001",
            "name": "R2-D2",
            "friends": [
                {"name": "Luke Skywalker"},
                {"name": "Han Solo"},
                {"name": "Leia Organa"},
            ],
        }
    }
    result = client.execute(query)
    assert result == expected


def test_nested_query(client):
    query = gql(
        """
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
        """
    )
    expected = {
        "hero": {
            "name": "R2-D2",
            "friends": [
                {
                    "name": "Luke Skywalker",
                    "appearsIn": ["NEWHOPE", "EMPIRE", "JEDI"],
                    "friends": [
                        {"name": "Han Solo"},
                        {"name": "Leia Organa"},
                        {"name": "C-3PO"},
                        {"name": "R2-D2"},
                    ],
                },
                {
                    "name": "Han Solo",
                    "appearsIn": ["NEWHOPE", "EMPIRE", "JEDI"],
                    "friends": [
                        {"name": "Luke Skywalker"},
                        {"name": "Leia Organa"},
                        {"name": "R2-D2"},
                    ],
                },
                {
                    "name": "Leia Organa",
                    "appearsIn": ["NEWHOPE", "EMPIRE", "JEDI"],
                    "friends": [
                        {"name": "Luke Skywalker"},
                        {"name": "Han Solo"},
                        {"name": "C-3PO"},
                        {"name": "R2-D2"},
                    ],
                },
            ],
        }
    }
    result = client.execute(query, parse_result=False)
    assert result == expected


def test_fetch_luke_query(client):
    query = gql(
        """
        query FetchLukeQuery {
          human(id: "1000") {
            name
          }
        }
        """
    )
    expected = {"human": {"name": "Luke Skywalker"}}
    result = client.execute(query)
    assert result == expected


def test_fetch_some_id_query(client):
    query = gql(
        """
        query FetchSomeIDQuery($someId: String!) {
          human(id: $someId) {
            name
          }
        }
        """
    )
    query.variable_values = {
        "someId": "1000",
    }
    expected = {"human": {"name": "Luke Skywalker"}}
    result = client.execute(query)
    assert result == expected


def test_fetch_some_id_query2(client):
    query = gql(
        """
        query FetchSomeIDQuery($someId: String!) {
          human(id: $someId) {
            name
          }
        }
        """
    )
    query.variable_values = {
        "someId": "1002",
    }
    expected = {"human": {"name": "Han Solo"}}
    result = client.execute(query)
    assert result == expected


def test_invalid_id_query(client):
    query = gql(
        """
        query humanQuery($id: String!) {
          human(id: $id) {
            name
          }
        }
        """
    )
    query.variable_values = {
        "id": "not a valid id",
    }
    expected = {"human": None}
    result = client.execute(query)
    assert result == expected


def test_fetch_luke_aliased(client):
    query = gql(
        """
        query FetchLukeAliased {
          luke: human(id: "1000") {
            name
          }
        }
        """
    )
    expected = {"luke": {"name": "Luke Skywalker"}}
    result = client.execute(query)
    assert result == expected


def test_fetch_luke_and_leia_aliased(client):
    query = gql(
        """
        query FetchLukeAndLeiaAliased {
          luke: human(id: "1000") {
            name
          }
          leia: human(id: "1003") {
            name
          }
        }
        """
    )
    expected = {"luke": {"name": "Luke Skywalker"}, "leia": {"name": "Leia Organa"}}
    result = client.execute(query)
    assert result == expected


def test_duplicate_fields(client):
    query = gql(
        """
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
        """
    )
    expected = {
        "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
        "leia": {"name": "Leia Organa", "homePlanet": "Alderaan"},
    }
    result = client.execute(query)
    assert result == expected


def test_use_fragment(client):
    query = gql(
        """
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
        """
    )
    expected = {
        "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
        "leia": {"name": "Leia Organa", "homePlanet": "Alderaan"},
    }
    result = client.execute(query)
    assert result == expected


def test_check_type_of_r2(client):
    query = gql(
        """
        query CheckTypeOfR2 {
          hero {
            __typename
            name
          }
        }
        """
    )
    expected = {"hero": {"__typename": "Droid", "name": "R2-D2"}}
    result = client.execute(query)
    assert result == expected


def test_check_type_of_luke(client):
    query = gql(
        """
        query CheckTypeOfLuke {
          hero(episode: EMPIRE) {
            __typename
            name
          }
        }
        """
    )
    expected = {"hero": {"__typename": "Human", "name": "Luke Skywalker"}}
    result = client.execute(query)
    assert result == expected


def test_parse_error(client):
    with pytest.raises(Exception) as exc_info:
        gql(
            """
            qeury
            """
        )
    error = exc_info.value
    assert isinstance(error, GraphQLError)
    assert "Syntax Error: Unexpected Name 'qeury'." in str(error)


def test_mutation_result(client):
    query = gql(
        """
        mutation CreateReviewForEpisode($ep: Episode!, $review: ReviewInput!) {
          createReview(episode: $ep, review: $review) {
            stars
            commentary
          }
        }
        """
    )
    query.variable_values = {
        "ep": "JEDI",
        "review": {"stars": 5, "commentary": "This is a great movie!"},
    }
    expected = {"createReview": {"stars": 5, "commentary": "This is a great movie!"}}
    result = client.execute(query)
    assert result == expected
