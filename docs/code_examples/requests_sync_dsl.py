from gql import Client
from gql.dsl import DSLQuery, DSLSchema, dsl_gql
from gql.transport.requests import RequestsHTTPTransport

transport = RequestsHTTPTransport(
    url="https://countries.trevorblades.com/", verify=True, retries=3,
)

client = Client(transport=transport, fetch_schema_from_transport=True)

# Using `with` on the sync client will start a connection on the transport
# and provide a `session` variable to execute queries on this connection.
# Because we requested to fetch the schema from the transport,
# GQL will fetch the schema just after the establishment of the first session
with client as session:

    # We should have received the schema now that the session is established
    assert client.schema is not None

    # Instantiate the root of the DSL Schema as ds
    ds = DSLSchema(client.schema)

    # Create the query using dynamically generated attributes from ds
    query = dsl_gql(
        DSLQuery(ds.Query.continents.select(ds.Continent.code, ds.Continent.name))
    )

    result = session.execute(query)
    print(result)
