import logging
import asyncio
import pytest
import sys

from gql import gql, AsyncClient
from gql.transport.websockets import WebsocketsTransport
from gql.transport.exceptions import TransportError
from graphql.execution import ExecutionResult
from typing import Dict
from .websocket_fixtures import MS

logging.basicConfig(level=logging.INFO)


@pytest.mark.online
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


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_invalid_query():

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
                bloh
              }
            }
        """
        )

        # Execute query
        result = await client.execute(query)

        # Verify result
        assert isinstance(result, ExecutionResult)

        assert result.data is None

        print(f"result = {repr(result.data)}, {repr(result.errors)}")
        assert result.errors is not None


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_sending_invalid_data():

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
              }
            }
        """
        )

        # Execute query
        result = await client.execute(query)

        # Verify result
        assert isinstance(result, ExecutionResult)

        print(f"result = {repr(result.data)}, {repr(result.errors)}")

        assert result.errors is None

        invalid_data = "QSDF"
        print(f">>> {invalid_data}")
        await sample_transport.websocket.send(invalid_data)

        await asyncio.sleep(2)


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_sending_invalid_payload():

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

    # Instanciate client
    async with AsyncClient(transport=sample_transport):

        invalid_payload = '{"id": "1", "type": "start", "payload": "BLAHBLAH"}'

        print(f">>> {invalid_payload}")
        await sample_transport.websocket.send(invalid_payload)

        await asyncio.sleep(2)


@pytest.mark.online
@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@pytest.mark.asyncio
async def test_websocket_sending_invalid_data_while_other_query_is_running():

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
              }
            }
        """
        )

        async def query_task1():
            await asyncio.sleep(2 * MS)

            with pytest.raises(TransportError):
                result = await client.execute(query)

                assert isinstance(result, ExecutionResult)
                assert result.errors is None

                assert isinstance(result.data, Dict)

                continents = result.data["continents"]

                africa = continents[0]
                assert africa["code"] == "AF"

        async def query_task2():

            invalid_data = "QSDF"
            print(f">>> {invalid_data}")
            await sample_transport.websocket.send(invalid_data)

        task1 = asyncio.create_task(query_task1())
        task2 = asyncio.create_task(query_task2())

        # await task1
        # await task2
        await asyncio.gather(task1, task2)


@pytest.mark.online
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
