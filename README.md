# GQL

This is a GraphQL client for Python.
Plays nicely with `graphene`, `graphql-core`, `graphql-js` and any other GraphQL implementation compatible with the spec.

GQL architecture is inspired by `React-Relay` and `Apollo-Client`.

[![travis][travis-image]][travis-url]
[![pyversion][pyversion-image]][pyversion-url]
[![pypi][pypi-image]][pypi-url]
[![Anaconda-Server Badge][conda-image]][conda-url]
[![coveralls][coveralls-image]][coveralls-url]

[travis-image]: https://img.shields.io/travis/graphql-python/gql.svg?style=flat
[travis-url]: https://travis-ci.org/graphql-python/gql
[pyversion-image]: https://img.shields.io/pypi/pyversions/gql
[pyversion-url]: https://pypi.org/project/gql/
[pypi-image]: https://img.shields.io/pypi/v/gql.svg?style=flat
[pypi-url]: https://pypi.org/project/gql/
[coveralls-image]: https://coveralls.io/repos/graphql-python/gql/badge.svg?branch=master&service=github
[coveralls-url]: https://coveralls.io/github/graphql-python/gql?branch=master
[conda-image]: https://img.shields.io/conda/vn/conda-forge/gql.svg
[conda-url]: https://anaconda.org/conda-forge/gql

## Installation

    $ pip install gql


## Usage

The example below shows how you can execute queries against a local schema.

```python
from gql import gql, Client

from .someSchema import SampleSchema


client = Client(schema=SampleSchema)
query = gql('''
    {
      hello
    }
''')

client.execute(query)
```

If you want to add additional headers when executing the query, you can specify these in a transport object:

```python
from gql import Client
from gql.transport.requests import RequestsHTTPTransport

from .someSchema import SampleSchema

client = Client(transport=RequestsHTTPTransport(
     url='/graphql', headers={'Authorization': 'token'}), schema=SampleSchema)
```

To execute against a graphQL API. (We get the schema by using introspection).

```python
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

sample_transport=RequestsHTTPTransport(
    url='https://countries.trevorblades.com/',
    use_json=True,
    headers={
        "Content-type": "application/json",
    },
    verify=False
)

client = Client(
    retries=3,
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

client.execute(query)
```

If you have a local schema stored as a `schema.graphql` file, you can do:

```python
from graphql import build_ast_schema, parse
from gql import gql, Client

with open('path/to/schema.graphql') as source:
    document = parse(source.read())

schema = build_ast_schema(document)

client = Client(schema=schema)
query = gql('''
    {
      hello
    }
''')

client.execute(query)
```

# Async clients and transports

It is possible to use async clients and transports using [asyncio](https://docs.python.org/3/library/asyncio.html).
Python3.6 is required for async clients and transports

## HTTP async transport

This transport uses the [aiohttp library](https://docs.aiohttp.org)

GraphQL subscriptions are not supported on this HTTP transport.
For subscriptions you should use the websockets transport.

```python
from gql import gql, AsyncClient
from gql.transport.aiohttp import AIOHTTPTransport
import asyncio

async def main():

    sample_transport = AIOHTTPTransport(
        url='https://countries.trevorblades.com/graphql',
        headers={'Authorization': 'token'}
    )

    async with AsyncClient(transport=sample_transport) as client:

        # Fetch schema (optional)
        await client.fetch_schema()

        # Execute single query
        query = gql('''
            query getContinents {
              continents {
                code
                name
              }
            }
        ''')

        result = await client.execute(query)

        print (f'result data = {result.data}, errors = {result.errors}')

asyncio.run(main())
```

## Websockets async transport

The websockets transport uses the apollo protocol described here:

[Apollo websockets transport protocol](https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md)

This transport allows to do multiple queries, mutations and subscriptions on the same websocket connection

```python
import logging
logging.basicConfig(level=logging.INFO)

from gql import gql, AsyncClient
from gql.transport.websockets import WebsocketsTransport
import asyncio

async def main():

    sample_transport = WebsocketsTransport(
        url='wss://countries.trevorblades.com/graphql',
        ssl=True,
        headers={'Authorization': 'token'}
    )

    async with AsyncClient(transport=sample_transport) as client:

        # Fetch schema (optional)
        await client.fetch_schema()

        # Execute single query
        query = gql('''
            query getContinents {
              continents {
                code
                name
              }
            }
        ''')
        result = await client.execute(query)
        print (f'result data = {result.data}, errors = {result.errors}')

        # Request subscription
        subscription = gql('''
            subscription {
                somethingChanged {
                    id
                }
            }
        ''')
        async for result in client.subscribe(subscription):
            print (f'result.data = {result.data}')

asyncio.run(main())
```

### Websockets SSL

If you need to connect to an ssl encrypted endpoint:

* use _wss_ instead of _ws_ in the url of the transport
* set the parameter ssl to True

```python
import ssl

sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    headers={'Authorization': 'token'},
    ssl=True
)
```

If you have a self-signed ssl certificate, you need to provide an ssl_context with the server public certificate:

```python
import pathlib
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
localhost_pem = pathlib.Path(__file__).with_name("YOUR_SERVER_PUBLIC_CERTIFICATE.pem")
ssl_context.load_verify_locations(localhost_pem)

sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    ssl=ssl_context
)
```

If you have also need to have a client ssl certificate, add:

```python
ssl_context.load_cert_chain(certfile='YOUR_CLIENT_CERTIFICATE.pem', keyfile='YOUR_CLIENT_CERTIFICATE_KEY.key')
```

### Websockets authentication

There are two ways to send authentication tokens with websockets depending on the server configuration.

1. Using HTTP Headers

```python
sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    headers={'Authorization': 'token'},
    ssl=True
)
```

2. With a payload in the connection_init websocket message

```python
sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    init_payload={'Authorization': 'token'},
    ssl=True
)
```

### Websockets advanced usage

It is possible to send multiple GraphQL queries (query, mutation or subscription) in parallel,
on the same websocket connection, using asyncio tasks

```python

async def execute_query1():
    result = await client.execute(query1)
    print (f'result data = {result.data}, errors = {result.errors}')

async def execute_query2():
    result = await client.execute(query2)
    print (f'result data = {result.data}, errors = {result.errors}')

async def execute_subscription1():
    async for result in client.subscribe(subscription1):
        print (f'result data = {result.data}, errors = {result.errors}')

async def execute_subscription2():
    async for result in client.subscribe(subscription2):
        print (f'result data = {result.data}, errors = {result.errors}')

task1 = asyncio.create_task(execute_query1())
task2 = asyncio.create_task(execute_query2())
task3 = asyncio.create_task(execute_subscription1())
task4 = asyncio.create_task(execute_subscription2())

await task1
await task2
await task3
await task4
```

Subscriptions tasks can be stopped at any time by running

```python
task.cancel()
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

[MIT License](https://github.com/graphql-python/gql/blob/master/LICENSE)
