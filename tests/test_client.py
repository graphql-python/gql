import os
from contextlib import suppress

import mock
import pytest
from graphql import build_ast_schema, parse

from gql import Client, GraphQLRequest, gql
from gql.transport import Transport
from gql.transport.exceptions import TransportQueryError

with suppress(ModuleNotFoundError):
    from urllib3.exceptions import NewConnectionError


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

    with pytest.raises(NotImplementedError) as exc_info:
        RandomTransport().execute_batch([])

    assert "This Transport has not implemented the execute_batch method" == str(
        exc_info.value
    )


@pytest.mark.aiohttp
def test_request_async_execute_batch_not_implemented_yet():
    from gql.transport.aiohttp import AIOHTTPTransport

    transport = AIOHTTPTransport(url="http://localhost/")
    client = Client(transport=transport)

    with pytest.raises(NotImplementedError) as exc_info:
        client.execute_batch([GraphQLRequest(document=gql("{dummy}"))])

    assert "Batching is not implemented for async yet." == str(exc_info.value)


@pytest.mark.requests
@mock.patch("urllib3.connection.HTTPConnection._new_conn")
def test_retries_on_transport(execute_mock):
    """Testing retries on the transport level

    This forces us to override low-level APIs because the retry mechanism on the urllib3
    (which uses requests) is pretty low-level itself.
    """
    from gql.transport.requests import RequestsHTTPTransport

    expected_retries = 3
    execute_mock.side_effect = NewConnectionError(
        "Should be HTTPConnection", "Fake connection error"
    )
    transport = RequestsHTTPTransport(
        url="http://127.0.0.1:8000/graphql",
        retries=expected_retries,
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
    with client as session:  # We're using the client as context manager
        with pytest.raises(Exception):
            session.execute(query)

    # This might look strange compared to the previous test, but making 3 retries
    # means you're actually doing 4 calls.
    assert execute_mock.call_count == expected_retries + 1

    execute_mock.reset_mock()
    queries = map(lambda d: GraphQLRequest(document=d), [query, query, query])

    with client as session:  # We're using the client as context manager
        with pytest.raises(Exception):
            session.execute_batch(queries)

    # This might look strange compared to the previous test, but making 3 retries
    # means you're actually doing 4 calls.
    assert execute_mock.call_count == expected_retries + 1


def test_no_schema_exception():
    with pytest.raises(AssertionError) as exc_info:
        client = Client()
        client.validate("")
    assert "Cannot validate the document locally, you need to pass a schema." in str(
        exc_info.value
    )


@pytest.mark.online
@pytest.mark.requests
def test_execute_result_error():

    from gql.transport.requests import RequestsHTTPTransport

    client = Client(
        transport=RequestsHTTPTransport(url="https://countries.trevorblades.com/"),
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

    with pytest.raises(TransportQueryError) as exc_info:
        client.execute(failing_query)
    assert 'Cannot query field "id" on type "Continent".' in str(exc_info.value)

    """
    Batching is not supported anymore on countries backend

    with pytest.raises(TransportQueryError) as exc_info:
        client.execute_batch([GraphQLRequest(document=failing_query)])
    assert 'Cannot query field "id" on type "Continent".' in str(exc_info.value)
    """


@pytest.mark.online
@pytest.mark.requests
def test_http_transport_verify_error(http_transport_query):
    from gql.transport.requests import RequestsHTTPTransport

    with Client(
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            verify=False,
        )
    ) as client:
        with pytest.warns(Warning) as record:
            client.execute(http_transport_query)

        assert len(record) == 1
        assert "Unverified HTTPS request is being made to host" in str(
            record[0].message
        )

        """
        Batching is not supported anymore on countries backend

        with pytest.warns(Warning) as record:
            client.execute_batch([GraphQLRequest(document=http_transport_query)])

        assert len(record) == 1
        assert "Unverified HTTPS request is being made to host" in str(
            record[0].message
        )
        """


@pytest.mark.online
@pytest.mark.requests
def test_http_transport_specify_method_valid(http_transport_query):
    from gql.transport.requests import RequestsHTTPTransport

    with Client(
        transport=RequestsHTTPTransport(
            url="https://countries.trevorblades.com/",
            method="POST",
        )
    ) as client:
        result = client.execute(http_transport_query)
        assert result is not None

        """
        Batching is not supported anymore on countries backend

        result = client.execute_batch([GraphQLRequest(document=http_transport_query)])
        assert result is not None
        """


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

    client = Client(schema=schema)
    result = client.execute(query)
    assert result["user"] is None


@pytest.mark.requests
def test_sync_transport_close_on_schema_retrieval_failure():
    """
    Ensure that the transport session is closed if an error occurs when
    entering the context manager (e.g., because schema retrieval fails)
    """

    from gql.transport.requests import RequestsHTTPTransport

    transport = RequestsHTTPTransport(url="http://localhost/")
    client = Client(transport=transport, fetch_schema_from_transport=True)

    try:
        with client:
            pass
    except Exception:
        # we don't care what exception is thrown, we just want to check if the
        # transport is closed afterwards
        pass

    assert client.transport.session is None


@pytest.mark.aiohttp
@pytest.mark.asyncio
async def test_async_transport_close_on_schema_retrieval_failure():
    """
    Ensure that the transport session is closed if an error occurs when
    entering the context manager (e.g., because schema retrieval fails)
    """

    from gql.transport.aiohttp import AIOHTTPTransport

    transport = AIOHTTPTransport(url="http://localhost/")
    client = Client(transport=transport, fetch_schema_from_transport=True)

    try:
        async with client:
            pass
    except Exception:
        # we don't care what exception is thrown, we just want to check if the
        # transport is closed afterwards
        pass

    assert client.transport.session is None
