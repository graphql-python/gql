# GQL

This is a GraphQL client for Python.
Plays nicely with `graphene`, `graphql-core`, `graphql-js` and any other GraphQL implementation compatible with the spec.

GQL architecture is inspired by `React-Relay` and `Apollo-Client`.

> **WARNING**: Please note that the following documentation describes the current version which is currently only available as a pre-release
> The documentation for the 2.x version compatible with python<3.6 is available in the [2.x branch](https://github.com/graphql-python/gql/tree/v2.x)

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

> **WARNING**: Please note that the following documentation describes the current version which is currently only available as a pre-release and needs to be installed with

    $ pip install --pre gql

## Usage

### Basic usage

```python
from gql import gql, Client, AIOHTTPTransport

# Select your transport with a defined url endpoint
transport = AIOHTTPTransport(url="https://countries.trevorblades.com/")

# Create a GraphQL client using the defined transport
client = Client(transport=transport, fetch_schema_from_transport=True)

# Provide a GraphQL query
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

# Execute the query on the transport
result = client.execute(query)
print(result)
```

### Local schema validation

It is possible to validate a query locally either using a provided schema or by using
[introspection](https://graphql.org/learn/introspection/) to get the schema from the GraphQL API server.

#### Using a provided schema

The schema can be provided as a String (which is usually stored in a .graphql file):

```python
with open('path/to/schema.graphql') as f:
    schema_str = f.read()

client = Client(schema=schema_str)
```

OR can be created using python classes:

```python
from .someSchema import SampleSchema
# SampleSchema is an instance of GraphQLSchema

client = Client(schema=SampleSchema)
```

See [tests/starwars/schema.py](tests/starwars/schema.py) for an example of such a schema.

#### Using introspection

In order to get the schema directly from the GraphQL Server API using the transport, you just need
to set the `fetch_schema_from_transport` argument of Client to True

### HTTP Headers

If you want to add additional http headers for your connection, you can specify these in your transport:

```python
transport = AIOHTTPTransport(url='YOUR_URL', headers={'Authorization': 'token'})
```

### GraphQL variables

You can also provide variable values with your query:

```python
query = gql(
    """
    query getContinentName ($code: ID!) {
      continent (code: $code) {
        name
      }
    }
"""
)

params = {"code": "EU"}

# Get name of continent with code "EU"
result = client.execute(query, variable_values=params)
print(result)

params = {"code": "AF"}

# Get name of continent with code "AF"
result = client.execute(query, variable_values=params)
print(result)
```

### GraphQL subscriptions

Using the websockets transport, it is possible to execute GraphQL subscriptions:

```python
from gql import gql, Client, WebsocketsTransport

transport = WebsocketsTransport(url='wss://your_server/graphql')

client = Client(
    transport=transport,
    fetch_schema_from_transport=True,
)

query = gql('''
    subscription yourSubscription {
        ...
    }
''')

for result in client.subscribe(query):
    print (result)
```

> **Note**: the websockets transport can also execute queries or mutations, it is not restricted to subscriptions

### Execute on a local schema

It is also possible to execute queries against a local schema (so without a transport).

```python
from gql import gql, Client

from .someSchema import SampleSchema

client = Client(schema=SampleSchema)

query = gql('''
    {
      hello
    }
''')

result = client.execute(query)
```

### Compose GraphQL queries dynamically with the DSL module

Instead of providing the GraphQL queries as a String, it is also possible to create GraphQL queries dynamically.
Using the DSL module, we can create a query using a Domain Specific Language which is created from the schema.

```python
from gql.dsl import DSLSchema

client = Client(schema=StarWarsSchema)
ds = DSLSchema(client)

query_dsl = ds.Query.hero.select(
    ds.Character.id,
    ds.Character.name,
    ds.Character.friends.select(ds.Character.name,),
)
```

will create a query equivalent to:

```
hero {
  id
  name
  friends {
    name
  }
}
```

See [tests/starwars/test_dsl.py](tests/starwars/test_dsl.py) for examples.

## Async usage with asyncio

When using the `execute` or `subscribe` function directly on the client, the execution is synchronous.
It means that we are blocked until we receive an answer from the server and
we cannot do anything else while waiting for this answer.

It is also possible to use this library asynchronously using [asyncio](https://docs.python.org/3/library/asyncio.html).

Async Features:
* Execute GraphQL subscriptions (See [using the websockets transport](#Websockets-async-transport))
* Execute GraphQL queries, mutations and subscriptions in parallel

To use the async features, you need to use an async transport:
* [AIOHTTPTransport](#HTTP-async-transport) for the HTTP(s) protocols
* [WebsocketsTransport](#Websockets-async-transport) for the ws(s) protocols

### HTTP async transport

This transport uses the [aiohttp library](https://docs.aiohttp.org)

GraphQL subscriptions are not supported on the HTTP transport.
For subscriptions you should use the websockets transport.

```python
from gql import gql, AIOHTTPTransport, Client
import asyncio

async def main():

    transport = AIOHTTPTransport(url='https://countries.trevorblades.com/graphql')

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with Client(
        transport=transport,
        fetch_schema_from_transport=True,
        ) as session:

        # Execute single query
        query = gql('''
            query getContinents {
              continents {
                code
                name
              }
            }
        ''')

        result = await session.execute(query)
        print(result)

asyncio.run(main())
```

### Websockets async transport

The websockets transport uses the apollo protocol described here:

[Apollo websockets transport protocol](https://github.com/apollographql/subscriptions-transport-ws/blob/master/PROTOCOL.md)

This transport allows to do multiple queries, mutations and subscriptions on the same websocket connection.

```python
import logging
logging.basicConfig(level=logging.INFO)

from gql import gql, Client, WebsocketsTransport
import asyncio

async def main():

    transport = WebsocketsTransport(url='wss://countries.trevorblades.com/graphql')

    # Using `async with` on the client will start a connection on the transport
    # and provide a `session` variable to execute queries on this connection
    async with Client(
        transport=sample_transport,
        fetch_schema_from_transport=True,
        ) as session:

        # Execute single query
        query = gql('''
            query getContinents {
              continents {
                code
                name
              }
            }
        ''')
        result = await session.execute(query)
        print(result)

        # Request subscription
        subscription = gql('''
            subscription {
                somethingChanged {
                    id
                }
            }
        ''')
        async for result in session.subscribe(subscription):
            print(result)

asyncio.run(main())
```

#### Websockets SSL

If you need to connect to an ssl encrypted endpoint:

* use _wss_ instead of _ws_ in the url of the transport

```python
sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    headers={'Authorization': 'token'}
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

#### Websockets authentication

There are two ways to send authentication tokens with websockets depending on the server configuration.

1. Using HTTP Headers

```python
sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    headers={'Authorization': 'token'}
)
```

2. With a payload in the connection_init websocket message

```python
sample_transport = WebsocketsTransport(
    url='wss://SERVER_URL:SERVER_PORT/graphql',
    init_payload={'Authorization': 'token'}
)
```

### Async advanced usage

It is possible to send multiple GraphQL queries (query, mutation or subscription) in parallel,
on the same websocket connection, using asyncio tasks.

In order to retry in case of connection failure, we can use the great
[backoff](https://github.com/litl/backoff) module.

```python
# First define all your queries using a session argument:

async def execute_query1(session):
    result = await session.execute(query1)
    print(result)

async def execute_query2(session):
    result = await session.execute(query2)
    print(result)

async def execute_subscription1(session):
    async for result in session.subscribe(subscription1):
        print(result)

async def execute_subscription2(session):
    async for result in session.subscribe(subscription2):
        print(result)

# Then create a couroutine which will connect to your API and run all your queries as tasks.
# We use a `backoff` decorator to reconnect using exponential backoff in case of connection failure.

@backoff.on_exception(backoff.expo, Exception, max_time=300)
async def graphql_connection():

    transport = WebsocketsTransport(url="wss://YOUR_URL")

    client = Client(transport=transport, fetch_schema_from_transport=True)

    async with client as session:
        task1 = asyncio.create_task(execute_query1(session))
        task2 = asyncio.create_task(execute_query2(session))
        task3 = asyncio.create_task(execute_subscription1(session))
        task4 = asyncio.create_task(execute_subscription2(session))

        await asyncio.gather(task1, task2, task3, task4)

asyncio.run(graphql_connection())
```

Subscriptions tasks can be stopped at any time by running

```python
task.cancel()
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

[MIT License](https://github.com/graphql-python/gql/blob/master/LICENSE)
