import asyncio

from gql import Client
from gql.dsl import DSLQuery, DSLSchema, dsl_gql
from gql.transport.aiohttp import AIOHTTPTransport


async def main():

    transport = AIOHTTPTransport(url="https://countries.trevorblades.com/graphql")

    client = Client(transport=transport, fetch_schema_from_transport=True)

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection.
    # Because we requested to fetch the schema from the transport,
    # GQL will fetch the schema just after the establishment of the first session
    async with client as session:

        # Instantiate the root of the DSL Schema as ds
        ds = DSLSchema(client.schema)

        # Create the query using dynamically generated attributes from ds
        query = dsl_gql(
            DSLQuery(
                ds.Query.continents(filter={"code": {"eq": "EU"}}).select(
                    ds.Continent.code, ds.Continent.name
                )
            )
        )

        result = await session.execute(query)
        print(result)

        # This can also be written as:

        # I want to query the continents
        query_continents = ds.Query.continents

        # I want to get only the continents with code equal to "EU"
        query_continents(filter={"code": {"eq": "EU"}})

        # I want this query to return the code and name fields
        query_continents.select(ds.Continent.code)
        query_continents.select(ds.Continent.name)

        # I generate a document from my query to be able to execute it
        query = dsl_gql(DSLQuery(query_continents))

        # Execute the query
        result = await session.execute(query)
        print(result)


asyncio.run(main())
