from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

sample_transport=RequestsHTTPTransport(
    url='https://countries.trevorblades.com/',
    verify=True,
    retries=3,
)

client = Client(
    transport=sample_transport,
    fetch_schema_from_transport=True,
)

query = gql('''
    query getContinents {
      continents {
        code
        name
      }
    }
''')

result = client.execute(query)
print(result)
