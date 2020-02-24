import pytest
import mock

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport


@mock.patch('gql.transport.requests.RequestsHTTPTransport.execute')
def test_retries(execute_mock):
    expected_retries = 3
    execute_mock.side_effect = Exception("fail")

    client = Client(
        retries=expected_retries,
        transport=RequestsHTTPTransport(url='http://swapi.graphene-python.org/graphql')
    )

    query = gql('''
    {
      myFavoriteFilm: film(id:"RmlsbToz") {
        id
        title
        episodeId
      }
    }
    ''')

    with pytest.raises(Exception):
        client.execute(query)

    assert execute_mock.call_count == expected_retries


def test_no_schema_exception():
    with pytest.raises(Exception) as excInfo:
        client = Client()
        client.validate('')
    assert "Cannot validate locally the document, you need to pass a schema." in str(excInfo.value)


def test_execute_result_error():
    expected_retries = 3

    client = Client(
        retries=expected_retries,
        transport=RequestsHTTPTransport(
            url='https://countries.trevorblades.com/',
            use_json=True,
            headers={
                "Content-type": "application/json",
            }
        )
    )

    query = gql('''
    query getContinents {
      continents {
        code
        name
        id
      }
    }
    ''')
    with pytest.raises(Exception) as excInfo:
        client.execute(query)
    assert "Cannot query field \"id\" on type \"Continent\"." in str(excInfo.value)
