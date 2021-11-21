import pytest
from graphql import GraphQLError

from gql import gql
from gql.utilities import parse_result
from tests.starwars.schema import StarWarsSchema


def test_hero_name_and_friends_query():
    query = gql(
        """
        query HeroNameAndFriendsQuery {
          hero {
            id
            friends {
              name
            }
            name
          }
        }
        """
    )
    result = {
        "hero": {
            "id": "2001",
            "friends": [
                {"name": "Luke Skywalker"},
                {"name": "Han Solo"},
                {"name": "Leia Organa"},
            ],
            "name": "R2-D2",
        }
    }

    parsed_result = parse_result(StarWarsSchema, query, result)

    assert result == parsed_result


def test_key_not_found_in_result():

    query = gql(
        """
        {
          hero {
            id
          }
        }
        """
    )

    # Backend returned an invalid result without the hero key
    # Should be impossible. In that case, we ignore the missing key
    result = {}

    parsed_result = parse_result(StarWarsSchema, query, result)

    assert result == parsed_result


def test_invalid_result_raise_error():

    query = gql(
        """
        {
          hero {
            id
          }
        }
        """
    )

    result = {"hero": 5}

    with pytest.raises(GraphQLError) as exc_info:

        parse_result(StarWarsSchema, query, result)

    assert "Invalid result for container of field id: 5" in str(exc_info)


def test_fragment():

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

    result = {
        "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
        "leia": {"name": "Leia Organa", "homePlanet": "Alderaan"},
    }

    parsed_result = parse_result(StarWarsSchema, query, result)

    assert result == parsed_result


def test_fragment_not_found():

    query = gql(
        """
        query UseFragment {
          luke: human(id: "1000") {
            ...HumanFragment
          }
        }
        """
    )

    result = {
        "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
    }

    with pytest.raises(GraphQLError) as exc_info:

        parse_result(StarWarsSchema, query, result)

    assert 'Fragment "HumanFragment" not found in document!' in str(exc_info)


def test_return_none_if_result_is_none():

    query = gql(
        """
        query {
          hero {
           id
          }
        }
        """
    )

    result = None

    assert parse_result(StarWarsSchema, query, result) is None


def test_null_result_is_allowed():

    query = gql(
        """
        query {
          hero {
           id
          }
        }
        """
    )

    result = {"hero": None}

    parsed_result = parse_result(StarWarsSchema, query, result)

    assert result == parsed_result


def test_inline_fragment():

    query = gql(
        """
        query UseFragment {
          luke: human(id: "1000") {
            ... on Human {
              name
              homePlanet
            }
          }
        }
        """
    )

    result = {
        "luke": {"name": "Luke Skywalker", "homePlanet": "Tatooine"},
    }

    parsed_result = parse_result(StarWarsSchema, query, result)

    assert result == parsed_result
