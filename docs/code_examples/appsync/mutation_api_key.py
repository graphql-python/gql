import asyncio
import os
import sys
from urllib.parse import urlparse

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.appsync_auth import AppSyncApiKeyAuthentication

# Uncomment the following lines to enable debug output
# import logging
# logging.basicConfig(level=logging.DEBUG)


async def main():

    # Should look like:
    # https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql
    url = os.environ.get("AWS_GRAPHQL_API_ENDPOINT")
    api_key = os.environ.get("AWS_GRAPHQL_API_KEY")

    if url is None or api_key is None:
        print("Missing environment variables")
        sys.exit()

    # Extract host from url
    host = str(urlparse(url).netloc)

    auth = AppSyncApiKeyAuthentication(host=host, api_key=api_key)

    transport = AIOHTTPTransport(url=url, auth=auth)

    async with Client(
        transport=transport, fetch_schema_from_transport=False,
    ) as session:

        query = gql(
            """
mutation createMessage($message: String!) {
  createMessage(input: {message: $message}) {
    id
    message
    createdAt
  }
}"""
        )

        variable_values = {"message": "Hello world!"}

        result = await session.execute(query, variable_values=variable_values)
        print(result)


asyncio.run(main())
