import pytest

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport
import requests

@pytest.fixture
def client():
    request = requests.get('https://fierce-crag-44069.herokuapp.com/graphql',
                           headers={
                               'Host': 'fierce-crag-44069.herokuapp.com',
                               'Accept': 'text/html',
                           })
    request.raise_for_status()
    csrf = request.cookies['csrftoken']

    return Client(
        transport=RequestsHTTPTransport(url='https://fierce-crag-44069.herokuapp.com/graphql',
                                        cookies={"csrftoken": csrf},
                                        headers={'x-csrftoken':  csrf}),
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
