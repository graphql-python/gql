import asyncio
import logging

from tenacity import retry, retry_if_exception_type, wait_exponential

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

logging.basicConfig(level=logging.INFO)


async def main():

    # Note: this example used the test backend from
    # https://github.com/slothmanxyz/typegraphql-ws-apollo
    transport = AIOHTTPTransport(url="ws://localhost:5000/graphql")

    client = Client(transport=transport)

    retry_connect = retry(
        retry=retry_if_exception_type(Exception),
        wait=wait_exponential(max=10),
    )
    session = await client.connect_async(reconnecting=True, retry_connect=retry_connect)

    num = 0

    while True:
        num += 1

        # Execute single query
        query = gql("mutation ($message: String!) {sendMessage(message: $message)}")

        query.variable_values = {"message": f"test {num}"}

        try:
            result = await session.execute(query)
            print(result)
        except Exception as e:
            print(f"Received exception {e}")

        await asyncio.sleep(1)


asyncio.run(main())
