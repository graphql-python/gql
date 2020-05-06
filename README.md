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
    verify=False,
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


## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

[MIT License](https://github.com/graphql-python/gql/blob/master/LICENSE)
