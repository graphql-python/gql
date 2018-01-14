import pytest
import mock

from pygql import Client, gql
from pygql.transport.requests import RequestsHTTPTransport


@mock.patch('pygql.transport.requests.RequestsHTTPTransport.execute')
def test_retries(execute_mock):
    expected_retries = 3
    execute_mock.side_effect =Exception("fail")

    client = Client(
        retries=expected_retries,
        transport=RequestsHTTPTransport(url='https://fierce-crag-44069.herokuapp.com/graphql')
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



