import asyncio
import logging

from gql import Client, gql
from gql.transport.aiohttp_websockets import AIOHTTPWebsocketsTransport

logging.basicConfig(level=logging.INFO)


async def main():

    transport = AIOHTTPWebsocketsTransport(
        url="wss://countries.trevorblades.com/graphql"
    )

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with Client(
        transport=transport,
    ) as session:

        # Execute single query
        query = gql(
            """
            query getContinents {
              continents {
                code
                name
              }
            }
        """
        )
        result = await session.execute(query)
        print(result)

        # Request subscription
        subscription = gql(
            """
            subscription {
                somethingChanged {
                    id
                }
            }
        """
        )
        async for result in session.subscribe(subscription):
            print(result)


asyncio.run(main())
