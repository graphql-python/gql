import logging
import asyncio
import pytest
import sys

from gql import gql, AsyncClient
from gql.transport.websockets import WebsocketsTransport
from graphql.execution import ExecutionResult
from typing import Dict

logging.basicConfig(level=logging.INFO)


@pytest.mark.asyncio
async def test_websocket_simple_query():

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

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

        continents = result.data["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"

        print(sys.version_info)


@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@pytest.mark.asyncio
async def test_websocket_two_queries_in_parallel_using_two_tasks():

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
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

            continents = result.data["continents"]

            africa = continents[0]
            assert africa["code"] == "AF"

        async def query_task2():
            result = await client.execute(query2)

            assert isinstance(result, ExecutionResult)
            assert result.errors is None

            assert isinstance(result.data, Dict)

            continents = result.data["continents"]

            africa = continents[0]
            assert africa["name"] == "Africa"

        task1 = asyncio.create_task(query_task1())
        task2 = asyncio.create_task(query_task2())

        await task1
        await task2
