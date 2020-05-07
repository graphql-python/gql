import asyncio
import pytest
import sys

from gql import gql, AsyncClient
from gql.transport.aiohttp import AIOHTTPTransport
from graphql.execution import ExecutionResult
from typing import Dict


@pytest.mark.online
@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["http", "https"])
async def test_aiohttp_simple_query(event_loop, protocol):

    # Create http or https url
    url = f"{protocol}://countries.trevorblades.com/graphql"

    # Get transport
    sample_transport = AIOHTTPTransport(url=url)

    # Instanciate client
    async with AsyncClient(transport=sample_transport) as client:

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

        # Fetch schema
        await client.fetch_schema()

        # Execute query
        result = await client.execute(query)

        # Verify result
        assert isinstance(result, ExecutionResult)
        assert result.errors is None

        assert isinstance(result.data, Dict)

        print(result.data)

        continents = result.data["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.online
@pytest.mark.asyncio
async def test_aiohttp_invalid_query(event_loop):

    sample_transport = AIOHTTPTransport(
        url="https://countries.trevorblades.com/graphql"
    )

    async with AsyncClient(transport=sample_transport) as client:

        query = gql(
            """
            query getContinents {
              continents {
                code
                bloh
              }
            }
        """
        )

        result = await client.execute(query)

        assert isinstance(result, ExecutionResult)

        assert result.data is None

        print(f"result = {repr(result.data)}, {repr(result.errors)}")
        assert result.errors is not None


@pytest.mark.online
@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@pytest.mark.asyncio
async def test_aiohttp_two_queries_in_parallel_using_two_tasks(event_loop):

    sample_transport = AIOHTTPTransport(
        url="https://countries.trevorblades.com/graphql",
    )

    # Instanciate client
    async with AsyncClient(transport=sample_transport) as client:

        query1 = gql(
            """
            query getContinents {
              continents {
                code
              }
            }
        """
        )

        query2 = gql(
            """
            query getContinents {
              continents {
                name
              }
            }
        """
        )

        async def query_task1():
            result = await client.execute(query1)

            assert isinstance(result, ExecutionResult)
            assert result.errors is None

            assert isinstance(result.data, Dict)

            print(result.data)

            continents = result.data["continents"]

            africa = continents[0]
            assert africa["code"] == "AF"

        async def query_task2():
            result = await client.execute(query2)

            assert isinstance(result, ExecutionResult)
            assert result.errors is None

            assert isinstance(result.data, Dict)

            print(result.data)

            continents = result.data["continents"]

            africa = continents[0]
            assert africa["name"] == "Africa"

        task1 = asyncio.create_task(query_task1())
        task2 = asyncio.create_task(query_task2())

        await task1
        await task2
