import pytest
import mock

from gql import Client, gql
from gql.client import ResultError
from gql.transport.requests import RequestsHTTPTransport


@mock.patch('gql.transport.requests.RequestsHTTPTransport.execute')
def test_retries(execute_mock, gql_query):
    expected_retries = 3
    execute_mock.side_effect = Exception("fail")

    client = Client(
        retries=expected_retries,
        transport=RequestsHTTPTransport(url='http://swapi.graphene-python.org/graphql')
    )

    with pytest.raises(Exception):
        client.execute(gql_query)

    assert execute_mock.call_count == expected_retries


@mock.patch('gql.transport.requests.RequestsHTTPTransport.execute')
def test_client_does_not_raise_exception(execute_mock, gql_query):
    mock_response = mock.Mock()
    mock_response.errors = None
    execute_mock.return_value = mock_response

    client = Client(
        transport=RequestsHTTPTransport(url='http://swapi.graphene-python.org/graphql'),
        raise_error=False
    )

    assert client.execute(gql_query)


@mock.patch('gql.transport.requests.RequestsHTTPTransport.execute')
def test_client_raises_error_exception(execute_mock, gql_query):

    mock_response = mock.Mock()
    mock_response.errors = [{'message': 'a real error'}]
    execute_mock.return_value = mock_response

    client = Client(
        transport=RequestsHTTPTransport(url='http://swapi.graphene-python.org/graphql'),
        raise_error=False
    )

    with pytest.raises(ResultError):
        client.execute(gql_query)


@mock.patch('gql.transport.requests.RequestsHTTPTransport.execute')
def test_client_returns_errors(execute_mock, gql_query):

    mock_response = mock.Mock()
    mock_response.errors = [{'message': 'a real error'}]
    execute_mock.return_value = mock_response

    client = Client(
        transport=RequestsHTTPTransport(url='http://swapi.graphene-python.org/graphql'),
        raise_error=True
    )

    response = client.execute(gql_query)
    assert response.errors == mock_response.errors
