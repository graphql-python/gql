import asyncio

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport


async def main():

    # Select your transport with a defined url endpoint
    transport = AIOHTTPTransport(url="https://countries.trevorblades.com/graphql")

    # Create a GraphQL client using the defined transport
    client = Client(transport=transport)

    # Provide a GraphQL query
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

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with client as session:

        # Execute the query
        result = await session.execute(query)
        print(result)


asyncio.run(main())
