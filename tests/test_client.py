import os

import mock
import pytest
from urllib3.exceptions import NewConnectionError

from graphql import build_ast_schema, parse

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport, Transport


@pytest.fixture
def http_transport_query():
    return gql(
        """
    query getContinents {
      continents {
        code
        name
      }
    }
    """
    )


def test_request_transport_not_implemented(http_transport_query):
    class RandomTransport(Transport):
        def execute(self):
            super(RandomTransport, self).execute(http_transport_query)

    with pytest.raises(NotImplementedError) as exc_info:
        RandomTransport().execute()
    assert "Any Transport subclass must implement execute method" == str(exc_info.value)


@mock.patch("gql.transport.requests.RequestsHTTPTransport.execute")
def test_retries(execute_mock):
    expected_retries = 3
    execute_mock.side_effect = Exception("fail")

    client = Client(
        retries=expected_retries,
        transport=RequestsHTTPTransport(url="http://swapi.graphene-python.org/graphql"),
    )

    query = gql(
        """
    {
      myFavoriteFilm: film(id:"RmlsbToz") {
        id
        title
        episodeId
      }
    }
    """
    )

    with pytest.raises(Exception):
        client.execute(query)
    client.close()
    assert execute_mock.call_count == expected_retries


@mock.patch("urllib3.connection.HTTPConnection._new_conn")
def test_retries_on_transport(execute_mock):
    """Testing retries on the transport level

    This forces us to override low-level APIs because the retry mechanism on the urllib3 (which
    uses requests) is pretty low-level itself.
    """
    expected_retries = 3
    execute_mock.side_effect = NewConnectionError(
        "Should be HTTPConnection", "Fake connection error"
    )
    transport = RequestsHTTPTransport(
        url="http://localhost:9999", retries=expected_retries,
    )
    client = Client(transport=transport)

    query = gql(
        """
    {
      myFavoriteFilm: film(id:"RmlsbToz") {
        id
        title
        episodeId
      }
    }
    """
    )
    with client:  # We're using the client as context manager
        with pytest.raises(Exception):
            client.execute(query)

    # This might look strange compared to the previous test, but making 3 retries
    # means you're actually doing 4 calls.
    assert execute_mock.call_count == expected_retries + 1


def test_no_schema_exception():
    with pytest.raises(Exception) as exc_info:
        client = Client()
        client.validate("")
    assert "Cannot validate locally the document, you need to pass a schema." in str(
        exc_info.value
    )


def test_execute_result_error():
    expected_retries = 3

    client = Client(
        retries=expected_retries,
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            use_json=True,
            headers={"Content-type": "application/json"},
        ),
    )

    failing_query = gql(
        """
    query getContinents {
      continents {
        code
        name
        id
      }
    }
    """
    )

    with pytest.raises(Exception) as exc_info:
        client.execute(failing_query)
    client.close()
    assert 'Cannot query field "id" on type "Continent".' in str(exc_info.value)


def test_http_transport_raise_for_status_error(http_transport_query):
    client = Client(
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            headers={"Content-type": "application/json"},
        )
    )

    with pytest.raises(Exception) as exc_info:
        client.execute(http_transport_query)
    client.close()
    assert "400 Client Error: Bad Request for url" in str(exc_info.value)


def test_http_transport_verify_error(http_transport_query):
    client = Client(
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            use_json=True,
            headers={"Content-type": "application/json"},
            verify=False,
        )
    )
    with pytest.warns(Warning) as record:
        client.execute(http_transport_query)
    client.close()  # We could have written `with client:` on top of the `with pytest...` instead
    assert len(record) == 1
    assert "Unverified HTTPS request is being made to host" in str(record[0].message)


def test_http_transport_specify_method_valid(http_transport_query):
    client = Client(
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            use_json=True,
            headers={"Content-type": "application/json"},
            method="POST",
        )
    )

    result = client.execute(http_transport_query)
    client.close()
    assert result is not None


def test_http_transport_specify_method_invalid(http_transport_query):
    client = Client(
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            use_json=True,
            headers={"Content-type": "application/json"},
            method="GET",
        )
    )

    with pytest.raises(Exception) as exc_info:
        client.execute(http_transport_query)
    client.close()
    assert "400 Client Error: Bad Request for url" in str(exc_info.value)


def test_gql():
    sample_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "fixtures",
        "graphql",
        "sample.graphql",
    )
    with open(sample_path) as source:
        document = parse(source.read())

    schema = build_ast_schema(document)

    client = Client(schema=schema)
    query = gql(
        """
        query getUser {
          user(id: "1000") {
            id
            username
          }
        }
    """
    )
    result = client.execute(query)
    client.close()
    assert result["user"] is None
