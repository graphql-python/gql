import asyncio

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport


async def main():

    transport = AIOHTTPTransport(url="https://countries.trevorblades.com/graphql")

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with Client(
        transport=transport, fetch_schema_from_transport=True,
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


asyncio.run(main())
