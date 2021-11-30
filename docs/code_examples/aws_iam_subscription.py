import asyncio
import logging
import os
import sys

from gql import Client, gql
from gql.transport.awsappsync import AppSyncWebsocketsTransport

logging.basicConfig(level=logging.DEBUG)


async def main():

    # Should look like:
    # https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql
    url = os.environ.get("AWS_GRAPHQL_API_ENDPOINT")
    api_key = os.environ.get("AWS_GRAPHQL_API_KEY")

    if url is None or api_key is None:
        print("Missing environment variables")
        sys.exit()

    # Using implicit auth (IAM)
    transport = AppSyncWebsocketsTransport(url=url)

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
