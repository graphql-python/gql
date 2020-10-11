gql-cli
=======

GQL provides a python 3.6+ script, called `gql-cli` which allows you to execute
GraphQL queries directly from the terminal.

This script supports http(s) or websockets transports.

Usage
-----

.. argparse::
   :module: gql.cli
   :func: get_parser
   :prog: gql-cli

Examples
--------

Simple query using https:

.. code-block:: shell

    echo 'query { continent(code:"AF") { name } }' | gql-cli https://countries.trevorblades.com

Simple query using websockets:

.. code-block:: shell

    echo 'query { continent(code:"AF") { name } }' | gql-cli wss://countries.trevorblades.com/graphql

Query with variable:

.. code-block:: shell

    echo 'query getContinent($code:ID!) { continent(code:$code) { name } }' | gql-cli https://countries.trevorblades.com --params code:AF

Interactive usage (insert your query in the terminal, then press Ctrl-D to execute it):

.. code-block:: shell

    gql-cli wss://countries.trevorblades.com/graphql --params code:AF

Execute query saved in a file:

.. code-block:: shell

    cat query.gql | gql-cli wss://countries.trevorblades.com/graphql
