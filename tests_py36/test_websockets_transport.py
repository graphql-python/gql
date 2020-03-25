import logging

logging.basicConfig(level=logging.INFO)

from gql import gql, Client
from gql.transport.websockets import WebsocketsTransport
from graphql.execution import ExecutionResult
from typing import Dict

import asyncio
import pytest

@pytest.mark.asyncio
async def test_websocket_query():

    # Get Websockets transport
    sample_transport = WebsocketsTransport(
        url='wss://countries.trevorblades.com/graphql',
        ssl=True
    )

    # Instanciate client
    client = Client(transport=sample_transport)

    query = gql('''
        query getContinents {
          continents {
            code
            name
          }
        }
    ''')

    # Fetch schema
    await client.fetch_schema()

    # Execute query
    result = await client.execute_async(query)

    # Verify result
    assert isinstance(result, ExecutionResult)
    assert result.errors == None

    assert isinstance(result.data, Dict)

    continents = result.data['continents']

    africa = continents[0]

    assert africa['code'] == 'AF'

    # Sleep 1 second to allow the connections to end
    await asyncio.sleep(1)
