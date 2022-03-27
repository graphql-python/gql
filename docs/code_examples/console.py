import asyncio
import logging

import backoff
from aioconsole import ainput

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportClosed

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
        self._session = None
        self._connect_task = None

        self._close_request_event = asyncio.Event()
        self._reconnect_request_event = asyncio.Event()

        self._connected_event = asyncio.Event()
        self._closed_event = asyncio.Event()

        self.get_continent_name_query = gql(GET_CONTINENT_NAME)

    @backoff.on_exception(backoff.expo, Exception, max_time=300)
    async def _connection_loop(self):

        while True:
            print("Connecting")
            try:
                async with self._client as session:
                    self._session = session
                    print("Connected")
                    self._connected_event.set()

                    # Wait for the close or reconnect event
                    self._close_request_event.clear()
                    self._reconnect_request_event.clear()

                    close_event_task = asyncio.create_task(
                        self._close_request_event.wait()
                    )
                    reconnect_event_task = asyncio.create_task(
                        self._reconnect_request_event.wait()
                    )

                    events = [close_event_task, reconnect_event_task]

                    done, pending = await asyncio.wait(
                        events, return_when=asyncio.FIRST_COMPLETED
                    )

                    for task in pending:
                        task.cancel()

                    if close_event_task in done:
                        # If we received a closed event, then we go out of the loop
                        break

                    # If we received a reconnect event,
                    # then we disconnect and connect again

            finally:
                self._session = None
                print("Disconnected")

        print("Closed")
        self._closed_event.set()

    async def connect(self):
        print("connect()")
        if self._connect_task:
            print("Already connected")
        else:
            self._connected_event.clear()
            self._connect_task = asyncio.create_task(self._connection_loop())
            await asyncio.wait_for(self._connected_event.wait(), timeout=10.0)

    async def close(self):
        print("close()")
        self._connect_task = None
        self._closed_event.clear()
        self._close_request_event.set()
        await asyncio.wait_for(self._closed_event.wait(), timeout=10.0)

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def execute(self, *args, **kwargs):
        try:
            answer = await self._session.execute(*args, **kwargs)
        except TransportClosed:
            self._reconnect_request_event.set()
            raise

        return answer

    async def get_continent_name(self, code):
        params = {"code": code}

        answer = await self.execute(
            self.get_continent_name_query, variable_values=params
        )

        return answer.get("continent").get("name")


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
