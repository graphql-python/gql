# GQL

This is a GraphQL client for Python.
Plays nicely with `graphene`, `graphql-core`, `graphql-js` and any other GraphQL implementation compatible with the spec.

GQL architecture is inspired by `React-Relay` and `Apollo-Client`.

[![travis][travis-image]][travis-url]
[![pypi][pypi-image]][pypi-url]
[![coveralls][coveralls-image]][coveralls-url]

[travis-image]: https://img.shields.io/travis/graphql-python/gql.svg?style=flat
[travis-url]: https://travis-ci.org/graphql-python/gql
[pypi-image]: https://img.shields.io/pypi/v/gql.svg?style=flat
[pypi-url]: https://pypi.python.org/pypi/gql
[coveralls-image]: https://coveralls.io/repos/graphql-python/gql/badge.svg?branch=master&service=github
[coveralls-url]: https://coveralls.io/github/graphql-python/gql?branch=master

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

To execute against a graphQL API. (We get the schema by using introspection).

```
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport

_transport = RequestsHTTPTransport(
    url='http://api.xxx/graphql',
    use_json=True,
)

client = Client(
    retries=3,
    transport=_transport,
    fetch_schema_from_transport=True,
)
query = gql('''
{
  hello
}
''')

client.execute(query)
```

If you have a local schema stored as a schema.graphql file, you can do:
```
from graphql import build_ast_schema, parse
from gql import gql, Client

with open('schema.graphql') as source:
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

## License

[MIT License](https://github.com/graphql-python/gql/blob/master/LICENSE)
