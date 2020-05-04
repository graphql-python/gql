import asyncio
import pytest
import json
import websockets
import graphql

from .websocket_fixtures import MS, server, TestServer
from graphql.execution import ExecutionResult
from gql import gql, AsyncClient
from gql.transport.websockets import WebsocketsTransport
from tests_py36.schema import StarWarsSchema, StarWarsTypeDef, StarWarsIntrospection


starwars_expected_one = {
    "stars": 3,
    "commentary": "Was expecting more stuff",
    "episode": "JEDI",
}

starwars_expected_two = {
    "stars": 5,
    "commentary": "This is a great movie!",
    "episode": "JEDI",
}


async def server_starwars(ws, path):
    await TestServer.send_connection_ack(ws)

    try:
        await ws.recv()

        reviews = [starwars_expected_one, starwars_expected_two]

        for review in reviews:

            data = '{{"type":"data","id":"1","payload":{{"data":{{"reviewAdded": {0}}}}}}}'.format(
                json.dumps(review)
            )
            await ws.send(data)
            await asyncio.sleep(2 * MS)

        await TestServer.send_complete(ws, 1)
        await TestServer.wait_connection_terminate(ws)

    except websockets.exceptions.ConnectionClosedOK:
        pass

    print("Server is now closed")


starwars_subscription_str = """
    subscription ListenEpisodeReviews($ep: Episode!) {
      reviewAdded(episode: $ep) {
        stars,
        commentary,
        episode
      }
    }
"""

starwars_invalid_subscription_str = """
    subscription ListenEpisodeReviews($ep: Episode!) {
      reviewAdded(episode: $ep) {
        not_valid_field,
        stars,
        commentary,
        episode
      }
    }
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_starwars], indirect=True)
@pytest.mark.parametrize("subscription_str", [starwars_subscription_str])
@pytest.mark.parametrize(
    "client_params",
    [
        {"schema": StarWarsSchema},
        {"introspection": StarWarsIntrospection},
        {"type_def": StarWarsTypeDef},
    ],
)
async def test_async_client_validation(
    event_loop, server, subscription_str, client_params
):

    url = "ws://" + server.hostname + ":" + str(server.port) + "/graphql"

    sample_transport = WebsocketsTransport(url=url)

    async with AsyncClient(transport=sample_transport, **client_params) as client:

        variable_values = {"ep": "JEDI"}

        subscription = gql(subscription_str)

        expected = []

        async for result in client.subscribe(
            subscription, variable_values=variable_values
        ):

            assert isinstance(result, ExecutionResult)
            assert result.errors is None

            review = result.data["reviewAdded"]
            expected.append(review)

            assert "stars" in review
            assert "commentary" in review
            assert "episode" in review

        assert expected[0] == starwars_expected_one
        assert expected[1] == starwars_expected_two


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_starwars], indirect=True)
@pytest.mark.parametrize("subscription_str", [starwars_invalid_subscription_str])
@pytest.mark.parametrize(
    "client_params",
    [
        {"schema": StarWarsSchema},
        {"introspection": StarWarsIntrospection},
        {"type_def": StarWarsTypeDef},
    ],
)
async def test_async_client_validation_invalid_query(
    event_loop, server, subscription_str, client_params
):

    url = "ws://" + server.hostname + ":" + str(server.port) + "/graphql"

    sample_transport = WebsocketsTransport(url=url)

    async with AsyncClient(transport=sample_transport, **client_params) as client:

        variable_values = {"ep": "JEDI"}

        subscription = gql(subscription_str)

        with pytest.raises(graphql.error.base.GraphQLError):
            async for result in client.subscribe(
                subscription, variable_values=variable_values
            ):
                pass


@pytest.mark.asyncio
@pytest.mark.parametrize("server", [server_starwars], indirect=True)
@pytest.mark.parametrize("subscription_str", [starwars_invalid_subscription_str])
@pytest.mark.parametrize(
    "client_params",
    [
        {"schema": StarWarsSchema, "introspection": StarWarsIntrospection},
        {"schema": StarWarsSchema, "type_def": StarWarsTypeDef},
        {"introspection": StarWarsIntrospection, "type_def": StarWarsTypeDef},
    ],
)
async def test_async_client_validation_different_schemas_parameters_forbidden(
    event_loop, server, subscription_str, client_params
):

    url = "ws://" + server.hostname + ":" + str(server.port) + "/graphql"

    sample_transport = WebsocketsTransport(url=url)

    with pytest.raises(AssertionError):
        async with AsyncClient(transport=sample_transport, **client_params):
            pass
