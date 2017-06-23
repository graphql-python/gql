import pytest

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport


@pytest.fixture
def client():
    return Client(
      transport=RequestsHTTPTransport(url='https://swapi.graphene-python.org/graphql'),
      fetch_schema_from_transport=True
    )


def test_hero_name_query(client):
    query = gql('''
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
    ''')
    expected = {
        "myFavoriteFilm": {
            "id": "RmlsbToz",
            "title": "Return of the Jedi",
            "episodeId": 6,
            "characters": {
                "edges": [
                  {
                      "node": {
                          "name": "Luke Skywalker"
                      }
                  },
                    {
                      "node": {
                          "name": "C-3PO"
                      }
                  },
                    {
                      "node": {
                          "name": "R2-D2"
                      }
                  },
                    {
                      "node": {
                          "name": "Darth Vader"
                      }
                  },
                    {
                      "node": {
                          "name": "Leia Organa"
                      }
                  }
                ]
            }
        }
    }
    result = client.execute(query)
    assert result == expected
