import asyncio
from asyncio import get_event_loop

import pytest
from graphql import subscribe
from graphql.execution.executors.asyncio import AsyncioExecutor

from gql import gql
from tests_py36.schema import StarWarsSchema


class ObservableAsyncIterable:
    def __init__(self, observable):
        self.disposable = None
        self.queue = asyncio.Queue()
        self.observable = observable

    def __aiter__(self):
        return self

    async def __anext__(self):
        type_, val = await self.queue.get()
        if type_ in ('E', 'C'):
            raise StopAsyncIteration()
        return val

    async def __aenter__(self):
        self.disposable = self.observable.subscribe(
            on_next=lambda val: self.queue.put_nowait(('N', val)),
            on_error=lambda exc: self.queue.put_nowait(('E', exc)),
            on_completed=lambda: self.queue.put_nowait(('C', None)),
        )
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        self.disposable.dispose()


@pytest.mark.asyncio
async def test_subscription_support():
    subs = gql('''
        subscription ListenEpisodeReviews($ep: Episode!) {
          reviewAdded(episode: $ep) {
            stars,
            commentary,
            episode
          }
        }
    ''')
    params = {
        'ep': 'JEDI'
    }
    expected_one = {
        'stars': 3,
        'commentary': 'Was expecting more stuff',
        'episode': 'JEDI'
    }
    expected_two = {
        'stars': 5,
        'commentary': 'This is a great movie!',
        'episode': 'JEDI'
    }
    # For asyncio, requires set return_promise=True as stated on the following comment
    # https://github.com/graphql-python/graphql-core/issues/63#issuecomment-568270864
    loop = get_event_loop()
    execution_result = await subscribe(
        schema=StarWarsSchema,
        document_ast=subs,
        return_promise=True,
        variable_values=params,
        executor=AsyncioExecutor(loop=loop)
    )
    expected = []
    async with ObservableAsyncIterable(execution_result) as oai:
        async for i in oai:
            review = i.to_dict()
            expected.append(review['data']['reviewAdded'])
    assert expected[0] == expected_one
    assert expected[1] == expected_two
