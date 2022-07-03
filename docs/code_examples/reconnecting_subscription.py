import asyncio
import logging

from gql import Client, gql
from gql.transport.websockets import WebsocketsTransport

logging.basicConfig(level=logging.INFO)


async def main():

    # Note: this example used the test backend from
    # https://github.com/slothmanxyz/typegraphql-ws-apollo
    transport = WebsocketsTransport(url="ws://localhost:5000/graphql")

    client = Client(transport=transport)

    session = await client.connect_async(reconnecting=True)

    query = gql("subscription {receiveMessage {message}}")

    while True:
        try:
            async for result in session.subscribe(query):
                print(result)
        except Exception as e:
            print(f"Received exception {e}")

        await asyncio.sleep(1)


asyncio.run(main())
