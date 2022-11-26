import asyncio
import sys
from typing import Dict

import pytest

from gql import Client, gql
from gql.transport.exceptions import TransportQueryError


@pytest.mark.httpx
@pytest.mark.online
@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", ["http", "https"])
async def test_httpx_simple_query(event_loop, protocol):

    from gql.transport.httpx import HTTPXAsyncTransport

    # Create http or https url
    url = f"{protocol}://countries.trevorblades.com/graphql"

    # Get transport
    sample_transport = HTTPXAsyncTransport(url=url)

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

        print(result)

        continents = result["continents"]

        africa = continents[0]

        assert africa["code"] == "AF"


@pytest.mark.httpx
@pytest.mark.online
@pytest.mark.asyncio
async def test_httpx_invalid_query(event_loop):

    from gql.transport.httpx import HTTPXAsyncTransport

    sample_transport = HTTPXAsyncTransport(
        url="https://countries.trevorblades.com/graphql"
    )

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

        with pytest.raises(TransportQueryError):
            await session.execute(query)


@pytest.mark.httpx
@pytest.mark.online
@pytest.mark.skipif(sys.version_info < (3, 8), reason="requires python3.8 or higher")
@pytest.mark.asyncio
async def test_httpx_two_queries_in_parallel_using_two_tasks(event_loop):

    from gql.transport.httpx import HTTPXAsyncTransport

    sample_transport = HTTPXAsyncTransport(
        url="https://countries.trevorblades.com/graphql",
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

            print(result)

            continents = result["continents"]

            africa = continents[0]
            assert africa["code"] == "AF"

        async def query_task2():
            result = await session.execute(query2)

            assert isinstance(result, Dict)

            print(result)

            continents = result["continents"]

            africa = continents[0]
            assert africa["name"] == "Africa"

        task1 = asyncio.create_task(query_task1())
        task2 = asyncio.create_task(query_task2())

        await task1
        await task2
