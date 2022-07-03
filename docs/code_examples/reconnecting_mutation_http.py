import asyncio
import logging

import backoff

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

logging.basicConfig(level=logging.INFO)


async def main():

    # Note: this example used the test backend from
    # https://github.com/slothmanxyz/typegraphql-ws-apollo
    transport = AIOHTTPTransport(url="ws://localhost:5000/graphql")

    client = Client(transport=transport)

    retry_connect = backoff.on_exception(
        backoff.expo,
        Exception,
        max_value=10,
        jitter=None,
    )
    session = await client.connect_async(reconnecting=True, retry_connect=retry_connect)

    num = 0

    while True:
        num += 1

        # Execute single query
        query = gql("mutation ($message: String!) {sendMessage(message: $message)}")

        params = {"message": f"test {num}"}

        try:
            result = await session.execute(query, variable_values=params)
            print(result)
        except Exception as e:
            print(f"Received exception {e}")

        await asyncio.sleep(1)


asyncio.run(main())
