# PYGQL

Is a fork of GQL and a GraphQL client for Python.
Plays nicely with `graphene`, `graphql-core`, `graphql-js` and any other GraphQL implementation compatible with the spec.

GQL architecture is inspired by `React-Relay` and `Apollo-Client`.

[![travis][travis-image]][travis-url]
[![coveralls][coveralls-image]][coveralls-url]

[travis-image]: https://img.shields.io/travis/itolosa/pygql.svg?style=flat
[travis-url]: https://travis-ci.org/itolosa/pygql
[coveralls-image]: https://coveralls.io/repos/itolosa/pygql/badge.svg?branch=master&service=github
[coveralls-url]: https://coveralls.io/github/itolosa/pygql?branch=master

## Installation

    $ pip install pygql


## Usage

The example below shows how you can execute queries against a local schema.


```python
from pygql import gql, Client

client = Client(schema=schema)
query = gql('''
{
  hello
}
''')

client.execute(query)
```

## License

[MIT License](https://github.com/itolosa/pygql/blob/master/LICENSE)
