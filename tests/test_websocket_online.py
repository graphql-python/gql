import asyncio
import logging
import sys
from typing import Dict

import pytest

from gql import Client, gql
from gql.transport.exceptions import TransportError, TransportQueryError

from .conftest import MS

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

logging.basicConfig(level=logging.INFO)


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_simple_query():
    from gql.transport.websockets import WebsocketsTransport

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql"
    )

    # Instanciate client
    async with Client(transport=sample_transport) as session:

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
        await session.fetch_schema()

        # Execute query
        result = await session.execute(query)

        # Verify result
        assert isinstance(result, Dict)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_invalid_query():
    from gql.transport.websockets import WebsocketsTransport

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

    # Instanciate client
    async with Client(transport=sample_transport) as session:

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
        with pytest.raises(TransportQueryError):
            await session.execute(query)


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_sending_invalid_data():
    from gql.transport.websockets import WebsocketsTransport

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

    # Instanciate client
    async with Client(transport=sample_transport) as session:

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
        result = await session.execute(query)

        print(f"result = {result!r}")

        invalid_data = "QSDF"
        print(f">>> {invalid_data}")
        await sample_transport.websocket.send(invalid_data)

        await asyncio.sleep(2)


@pytest.mark.online
@pytest.mark.asyncio
async def test_websocket_sending_invalid_payload():
    from gql.transport.websockets import WebsocketsTransport

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

    # Instanciate client
    async with Client(transport=sample_transport):

        invalid_payload = '{"id": "1", "type": "start", "payload": "BLAHBLAH"}'

        print(f">>> {invalid_payload}")
        await sample_transport.websocket.send(invalid_payload)

        await asyncio.sleep(2)


@pytest.mark.online
@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@pytest.mark.asyncio
async def test_websocket_sending_invalid_data_while_other_query_is_running():
    from gql.transport.websockets import WebsocketsTransport

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

    # Instanciate client
    async with Client(transport=sample_transport) as session:

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
                result = await session.execute(query)

                assert isinstance(result, Dict)

                continents = result["continents"]

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
    from gql.transport.websockets import WebsocketsTransport

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql", ssl=True
    )

    # Instanciate client
    async with Client(transport=sample_transport) as session:

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
            result = await session.execute(query1)

            assert isinstance(result, Dict)

            continents = result["continents"]

            africa = continents[0]
            assert africa["code"] == "AF"

        async def query_task2():
            result = await session.execute(query2)

            assert isinstance(result, Dict)

            continents = result["continents"]

            africa = continents[0]
            assert africa["name"] == "Africa"

        task1 = asyncio.create_task(query_task1())
        task2 = asyncio.create_task(query_task2())

        await task1
        await task2
