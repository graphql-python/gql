import asyncio
import logging
from typing import Optional

from aioconsole import ainput

from gql import Client, gql
from gql.client import AsyncClientSession
from gql.transport.aiohttp import AIOHTTPTransport

logging.basicConfig(level=logging.INFO)

GET_CONTINENT_NAME = """
    query getContinentName ($code: ID!) {
      continent (code: $code) {
        name
      }
    }
"""


class GraphQLContinentClient:
    def __init__(self):
        self._client = Client(
            transport=AIOHTTPTransport(url="https://countries.trevorblades.com/")
        )
        self._session: Optional[AsyncClientSession] = None

        self.get_continent_name_query = gql(GET_CONTINENT_NAME)

    async def connect(self):
        self._session = await self._client.connect_async(reconnecting=True)

    async def close(self):
        await self._client.close_async()

    async def get_continent_name(self, code):
        self.get_continent_name_query.variable_values = {"code": code}

        assert self._session is not None

        answer = await self._session.execute(self.get_continent_name_query)

        return answer.get("continent").get("name")  # type: ignore


async def main():
    continent_client = GraphQLContinentClient()

    continent_codes = ["AF", "AN", "AS", "EU", "NA", "OC", "SA"]

    await continent_client.connect()

    while True:

        answer = await ainput("\nPlease enter a continent code or 'exit':")
        answer = answer.strip()

        if answer == "exit":
            break
        elif answer in continent_codes:

            try:
                continent_name = await continent_client.get_continent_name(answer)
                print(f"The continent name is {continent_name}\n")
            except Exception as exc:
                print(f"Received exception {exc} while trying to get continent name")

        else:
            print(f"Please enter a valid continent code from {continent_codes}")

    await continent_client.close()


asyncio.run(main())
