import asyncio

from tests.starwars.fixtures import reviews


async def reviewAdded(episode):
    count = 0
    while count < len(reviews[episode]):
        yield reviews[episode][count]
        await asyncio.sleep(1)
        count += 1
