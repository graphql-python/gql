import json
from typing import Mapping

import pytest
from graphql import print_ast

from gql import gql
from gql.transport.exceptions import TransportConnectionFailed

# Marking all tests in this file with the websockets marker
pytestmark = pytest.mark.websockets

query1_str = """
    query getContinents {
      continents {
        code
        name
      }
    }
"""

query1_server_answer = (
    '{{"type":"data","id":"{query_id}","payload":{{"data":{{"continents":['
    '{{"code":"AF","name":"Africa"}},{{"code":"AN","name":"Antarctica"}},'
    '{{"code":"AS","name":"Asia"}},{{"code":"EU","name":"Europe"}},'
    '{{"code":"NA","name":"North America"}},{{"code":"OC","name":"Oceania"}},'
    '{{"code":"SA","name":"South America"}}]}}}}}}'
)

server1_answers = [
    query1_server_answer,
]


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websockets_adapter_simple_query(server):
    from gql.transport.common.adapters.websockets import WebSocketsAdapter

    url = f"ws://{server.hostname}:{server.port}/graphql"

    query = print_ast(gql(query1_str).document)
    print("query=", query)

    adapter = WebSocketsAdapter(url)

    await adapter.connect()

    init_message = json.dumps({"type": "connection_init", "payload": {}})

    await adapter.send(init_message)

    result = await adapter.receive()
    print(f"result={result}")

    payload = json.dumps({"query": query})
    query_message = json.dumps({"id": 1, "type": "start", "payload": payload})

    await adapter.send(query_message)

    result = await adapter.receive()
    print(f"result={result}")

    await adapter.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server1_answers], indirect=True)
async def test_websockets_adapter_edge_cases(server):
    from gql.transport.common.adapters.websockets import WebSocketsAdapter

    url = f"ws://{server.hostname}:{server.port}/graphql"

    query = print_ast(gql(query1_str).document)
    print("query=", query)

    adapter = WebSocketsAdapter(url, headers={"a": "r1"}, ssl=False, connect_args={})

    await adapter.connect()

    assert isinstance(adapter.headers, Mapping)
    assert adapter.headers["a"] == "r1"
    assert adapter.ssl is False
    assert adapter.connect_args == {}
    assert adapter.response_headers["dummy"] == "test1234"

    # Connect twice causes AssertionError
    with pytest.raises(AssertionError):
        await adapter.connect()

    await adapter.close()

    # Second close call is ignored
    await adapter.close()

    with pytest.raises(TransportConnectionFailed):
        await adapter.send("Blah")

    with pytest.raises(TransportConnectionFailed):
        await adapter.receive()
