import asyncio
import logging
import os
import sys
from urllib.parse import urlparse

from gql import Client, gql
from gql.transport.awsappsync import (
    AppSyncApiKeyAuthorization,
    AppSyncWebsocketsTransport,
)

logging.basicConfig(level=logging.DEBUG)


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

    print(f"Host: {host}")

    auth = AppSyncApiKeyAuthorization(host=host, api_key=api_key)

    transport = AppSyncWebsocketsTransport(url=url, authorization=auth)

    async with Client(transport=transport) as session:

        subscription = gql(
            """
subscription onCreateMessage {
  onCreateMessage {
    message
  }
}
"""
        )

        async for result in session.subscribe(subscription):
            print(result)


asyncio.run(main())
