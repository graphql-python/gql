import asyncio

import pytest
from graphql import ExecutionResult, GraphQLError, subscribe

from gql import Client, gql

from .fixtures import reviews
from .schema import StarWarsSchema

subscription_str = """
    subscription ListenEpisodeReviews($ep: Episode!) {
      reviewAdded(episode: $ep) {
        stars,
        commentary,
        episode
      }
    }
"""


async def await_if_coroutine(obj):
    """Function to make tests work for graphql-core versions before and after 3.3.0a3"""
    if asyncio.iscoroutine(obj):
        return await obj

    return obj


@pytest.mark.asyncio
async def test_subscription_support():
    # reset review data for this test
    reviews[6] = [
        {"stars": 3, "commentary": "Was expecting more stuff", "episode": 6},
        {"stars": 5, "commentary": "This is a great movie!", "episode": 6},
    ]

    subs = gql(subscription_str)

    params = {"ep": "JEDI"}
    expected = [{**review, "episode": "JEDI"} for review in reviews[6]]

    ai = await await_if_coroutine(
        subscribe(StarWarsSchema, subs.document, variable_values=params)
    )

    result = [result.data["reviewAdded"] async for result in ai]

    assert result == expected


@pytest.mark.asyncio
async def test_subscription_support_using_client():
    # reset review data for this test
    reviews[6] = [
        {"stars": 3, "commentary": "Was expecting more stuff", "episode": 6},
        {"stars": 5, "commentary": "This is a great movie!", "episode": 6},
    ]

    subs = gql(subscription_str)

    subs.variable_values = {"ep": "JEDI"}
    expected = [{**review, "episode": "JEDI"} for review in reviews[6]]

    async with Client(schema=StarWarsSchema) as session:
        results = [
            result["reviewAdded"]
            async for result in await await_if_coroutine(
                session.subscribe(subs, parse_result=False)
            )
        ]

    assert results == expected


subscription_invalid_str = """
    subscription ListenEpisodeReviews($ep: Episode!) {
      qsdfqsdfqsdf
    }
"""


@pytest.mark.asyncio
async def test_subscription_support_using_client_invalid_field():

    subs = gql(subscription_invalid_str)

    subs.variable_values = {"ep": "JEDI"}

    async with Client(schema=StarWarsSchema) as session:

        # We subscribe directly from the transport to avoid local validation
        results = [
            result
            async for result in await await_if_coroutine(
                session.transport.subscribe(subs)
            )
        ]

    assert len(results) == 1
    result = results[0]
    assert isinstance(result, ExecutionResult)
    assert result.data is None
    assert isinstance(result.errors, list)
    assert len(result.errors) == 1
    error = result.errors[0]
    assert isinstance(error, GraphQLError)
    assert error.message == "The subscription field 'qsdfqsdfqsdf' is not defined."
