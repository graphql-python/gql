.. _gql_cli:

gql-cli
=======

GQL provides a python 3.7+ script, called `gql-cli` which allows you to execute
GraphQL queries directly from the terminal.

This script supports http(s) or websockets protocols.

Usage
-----

.. argparse::
   :module: gql.cli
   :func: get_parser
   :prog: gql-cli

Examples
--------

Simple query using https
^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

    $ echo 'query { continent(code:"AF") { name } }' | gql-cli https://countries.trevorblades.com
    {"continent": {"name": "Africa"}}

Simple query using websockets
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

    $ echo 'query { continent(code:"AF") { name } }' | gql-cli wss://countries.trevorblades.com/graphql
    {"continent": {"name": "Africa"}}

Query with variable
^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

    $ echo 'query getContinent($code:ID!) { continent(code:$code) { name } }' | gql-cli https://countries.trevorblades.com --variables code:AF
    {"continent": {"name": "Africa"}}

Interactive usage
^^^^^^^^^^^^^^^^^

Insert your query in the terminal, then press Ctrl-D to execute it.

.. code-block:: shell

    $ gql-cli wss://countries.trevorblades.com/graphql --variables code:AF

Execute query saved in a file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Put the query in a file:

.. code-block:: shell

    $ echo 'query {
      continent(code:"AF") {
        name
      }
    }' > query.gql

Then execute query from the file:

.. code-block:: shell

    $ cat query.gql | gql-cli wss://countries.trevorblades.com/graphql
    {"continent": {"name": "Africa"}}

Print the GraphQL schema in a file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: shell

    $ gql-cli https://countries.trevorblades.com/graphql --print-schema > schema.graphql

.. note::

    By default, deprecated input fields are not requested from the backend.
    You can add :code:`--schema-download input_value_deprecation:true` to request them.

.. note::

    You can add :code:`--schema-download descriptions:false` to request a compact schema
    without comments.
