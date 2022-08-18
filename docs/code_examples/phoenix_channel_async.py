import asyncio

from gql import Client, gql
from gql.transport.phoenix_channel_websockets import PhoenixChannelWebsocketsTransport


async def main():

    transport = PhoenixChannelWebsocketsTransport(
        channel_name="YOUR_CHANNEL", url="wss://YOUR_URL/graphql"
    )

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with Client(transport=transport) as session:

        # Execute single query
        query = gql(
            """
            query yourQuery {
                ...
            }
        """
        )

        result = await session.execute(query)
        print(result)


asyncio.run(main())
