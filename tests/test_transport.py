import os

import pytest

from gql import Client, gql

# We serve https://github.com/graphql-python/swapi-graphene locally:
URL = "http://127.0.0.1:8000/graphql"

# Marking all tests in this file with the requests marker
pytestmark = pytest.mark.requests


def use_cassette(name):
    import vcr

    query_vcr = vcr.VCR(
        cassette_library_dir=os.path.join(
            os.path.dirname(__file__), "fixtures", "vcr_cassettes"
        ),
        record_mode="new_episodes",
        match_on=["uri", "method", "body"],
    )

    return query_vcr.use_cassette(name + ".yaml")


@pytest.fixture
def client():
    import requests
    from gql.transport.requests import RequestsHTTPTransport

    with use_cassette("client"):
        response = requests.get(
            URL, headers={"Host": "swapi.graphene-python.org", "Accept": "text/html"}
        )
        response.raise_for_status()
        csrf = response.cookies["csrftoken"]

        return Client(
            transport=RequestsHTTPTransport(
                url=URL, cookies={"csrftoken": csrf}, headers={"x-csrftoken": csrf}
            ),
            fetch_schema_from_transport=True,
        )


def test_hero_name_query(client):
    query = gql(
        """
        {
          myFavoriteFilm: film(id:"RmlsbToz") {
            id
            title
            episodeId
            characters(first:5) {
              edges {
                node {
                  name
                }
              }
            }
          }
        }
        """
    )
    expected = {
        "myFavoriteFilm": {
            "id": "RmlsbToz",
            "title": "Return of the Jedi",
            "episodeId": 6,
            "characters": {
                "edges": [
                    {"node": {"name": "Luke Skywalker"}},
                    {"node": {"name": "C-3PO"}},
                    {"node": {"name": "R2-D2"}},
                    {"node": {"name": "Darth Vader"}},
                    {"node": {"name": "Leia Organa"}},
                ]
            },
        }
    }
    with use_cassette("queries"):
        result = client.execute(query)
    assert result == expected


def test_query_with_variable(client):
    query = gql(
        """
        query Planet($id: ID!) {
          planet(id: $id) {
            id
            name
          }
        }
        """
    )
    expected = {"planet": {"id": "UGxhbmV0OjEw", "name": "Kamino"}}
    with use_cassette("queries"):
        result = client.execute(query, variable_values={"id": "UGxhbmV0OjEw"})
    assert result == expected


def test_named_query(client):
    query = gql(
        """
        query Planet1 {
          planet(id: "UGxhbmV0OjEw") {
            id
            name
          }
        }
        query Planet2 {
          planet(id: "UGxhbmV0OjEx") {
            id
            name
          }
        }
        """
    )
    expected = {"planet": {"id": "UGxhbmV0OjEx", "name": "Geonosis"}}
    with use_cassette("queries"):
        result = client.execute(query, operation_name="Planet2")
    assert result == expected


def test_header_query(client):
    query = gql(
        """
        query Planet($id: ID!) {
          planet(id: $id) {
            id
            name
          }
        }
        """
    )
    expected = {"planet": {"id": "UGxhbmV0OjEx", "name": "Geonosis"}}
    with use_cassette("queries"):
        result = client.execute(
            query, extra_args={"headers": {"authorization": "xxx-123"}}
        )
    assert result == expected
