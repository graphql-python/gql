import os
import pytest
import requests
import vcr

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport

# https://github.com/graphql-python/swapi-graphene
URL = "http://127.0.0.1:8000/graphql"


def use_cassette(name):
    return vcr.use_cassette(
        os.path.join(
            os.path.dirname(__file__), "fixtures", "vcr_cassettes", name + ".yaml"
        )
    )


@pytest.fixture
def client():
    with use_cassette("client"):
        request = requests.get(
            URL, headers={"Host": "swapi.graphene-python.org", "Accept": "text/html"}
        )
        request.raise_for_status()
        csrf = request.cookies["csrftoken"]

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
    with use_cassette("execute"):
        result = client.execute(query)
        assert result == expected
