from gql import Client, gql
from gql.transport.httpx import HTTPXTransport

transport = HTTPXTransport(url="https://countries.trevorblades.com/")

client = Client(transport=transport, fetch_schema_from_transport=True)

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

result = client.execute(query)
print(result)
