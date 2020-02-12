# GQL

This is a GraphQL client for Python.
Plays nicely with `graphene`, `graphql-core`, `graphql-js` and any other GraphQL implementation compatible with the spec.

GQL architecture is inspired by `React-Relay` and `Apollo-Client`.

[![travis][travis-image]][travis-url]
[![pypi][pypi-image]][pypi-url]
[![Anaconda-Server Badge][conda-image]][conda-url]
[![coveralls][coveralls-image]][coveralls-url]

[travis-image]: https://img.shields.io/travis/graphql-python/gql.svg?style=flat
[travis-url]: https://travis-ci.org/graphql-python/gql
[pypi-image]: https://img.shields.io/pypi/v/gql.svg?style=flat
[pypi-url]: https://pypi.python.org/pypi/gql
[coveralls-image]: https://coveralls.io/repos/graphql-python/gql/badge.svg?branch=master&service=github
[coveralls-url]: https://coveralls.io/github/graphql-python/gql?branch=master
[conda-image]: https://anaconda.org/conda-forge/gql/badges/version.svg
[conda-url]: https://anaconda.org/conda-forge/gql

## Installation

    $ pip install gql


## Usage

The example below shows how you can execute queries against a local schema.

```python
from gql import gql, Client

client = Client(schema=schema)
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

client = Client(transport=RequestsHTTPTransport(
     url='/graphql', headers={'Authorization': 'token'}), schema=schema)
```

## License

[MIT License](https://github.com/graphql-python/gql/blob/master/LICENSE)
