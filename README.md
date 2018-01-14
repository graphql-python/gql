# GQL

This is a GraphQL client for Python.
Plays nicely with `graphene`, `graphql-core`, `graphql-js` and any other GraphQL implementation compatible with the spec.

GQL architecture is inspired by `React-Relay` and `Apollo-Client`.

[![travis][travis-image]][travis-url]
[![coveralls][coveralls-image]][coveralls-url]

[travis-image]: https://img.shields.io/travis/itolosa/gql.svg?style=flat
[travis-url]: https://travis-ci.org/itolosa/gql
[coveralls-image]: https://coveralls.io/repos/itolosa/gql/badge.svg?branch=master&service=github
[coveralls-url]: https://coveralls.io/github/itolosa/gql?branch=master

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

## License

[MIT License](https://github.com/graphql-python/gql/blob/master/LICENSE)
