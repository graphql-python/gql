import asyncio
import logging

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

logging.basicConfig(level=logging.INFO)


async def main():

    transport = AIOHTTPTransport(url="https://gql-book-server.fly.dev/graphql")

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with Client(
        transport=transport,
    ) as session:

        # Request subscription
        subscription = gql(
            """
            subscription {
              book {
                title
                author
              }
            }
        """
        )

        # Subscribe and receive streaming updates
        async for result in session.subscribe(subscription):
            print(f"Received: {result}")


asyncio.run(main())
