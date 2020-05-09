import pytest

from gql import gql, AsyncClient
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.requests import RequestsHTTPTransport


@pytest.mark.online
@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["http", "https"])
@pytest.mark.parametrize("fetch_schema_from_transport", [True, False])
async def test_async_client_async_transport(
    event_loop, protocol, fetch_schema_from_transport
):

    # Create http or https url
    url = f"{protocol}://countries.trevorblades.com/graphql"

    # Get async transport
    sample_transport = AIOHTTPTransport(url=url)

    # Instanciate client
    async with AsyncClient(
        transport=sample_transport,
        fetch_schema_from_transport=fetch_schema_from_transport,
    ) as session:

        query = gql(
            """
            query getContinents {
              continents {
                code
                name
              }
            }
        """
        )

        # Execute query
        result = await session.execute(query)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

        if fetch_schema_from_transport:
            assert session.client.schema is not None


@pytest.mark.online
@pytest.mark.asyncio
@pytest.mark.parametrize("fetch_schema_from_transport", [True, False])
async def test_async_client_sync_transport(event_loop, fetch_schema_from_transport):

    url = "http://countries.trevorblades.com/graphql"

    # Get sync transport
    sample_transport = RequestsHTTPTransport(url=url, use_json=True)

    # Impossible to use a sync transport asynchronously
    with pytest.raises(AssertionError):
        async with AsyncClient(
            transport=sample_transport,
            fetch_schema_from_transport=fetch_schema_from_transport,
        ):
            pass

    sample_transport.close()


@pytest.mark.online
@pytest.mark.parametrize("protocol", ["http", "https"])
@pytest.mark.parametrize("fetch_schema_from_transport", [True, False])
def test_sync_client_async_transport(protocol, fetch_schema_from_transport):

    # Create http or https url
    url = f"{protocol}://countries.trevorblades.com/graphql"

    # Get async transport
    sample_transport = AIOHTTPTransport(url=url)

    # Instanciate client
    client = AsyncClient(
        transport=sample_transport,
        fetch_schema_from_transport=fetch_schema_from_transport,
    )

    query = gql(
        """
        query getContinents {
          continents {
            code
            name
          }
        }
    """
    )

    # Execute query synchronously
    result = client.execute(query)

    continents = result["continents"]

    africa = continents[0]

    assert africa["code"] == "AF"

    if fetch_schema_from_transport:
        assert client.schema is not None


@pytest.mark.online
@pytest.mark.parametrize("protocol", ["http", "https"])
@pytest.mark.parametrize("fetch_schema_from_transport", [True, False])
def test_sync_client_sync_transport(protocol, fetch_schema_from_transport):

    # Create http or https url
    url = f"{protocol}://countries.trevorblades.com/graphql"

    # Get sync transport
    sample_transport = RequestsHTTPTransport(url=url, use_json=True)

    # Instanciate client
    client = AsyncClient(
        transport=sample_transport,
        fetch_schema_from_transport=fetch_schema_from_transport,
    )

    query = gql(
        """
        query getContinents {
          continents {
            code
            name
          }
        }
    """
    )

    # Execute query synchronously
    result = client.execute(query)

    continents = result["continents"]

    africa = continents[0]

    assert africa["code"] == "AF"

    if fetch_schema_from_transport:
        assert client.schema is not None
