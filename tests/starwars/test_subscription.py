import pytest
from graphql import subscribe

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

    ai = await subscribe(StarWarsSchema, subs, variable_values=params)

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

    params = {"ep": "JEDI"}
    expected = [{**review, "episode": "JEDI"} for review in reviews[6]]

    async with Client(schema=StarWarsSchema) as session:
        results = [
            result["reviewAdded"]
            async for result in session.subscribe(subs, variable_values=params)
        ]

    assert results == expected
