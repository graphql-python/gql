Using variables
===============

It is possible to provide variable values with your query by providing a Dict to
the variable_values attribute of your query.

The variable values will be sent alongside the query in the transport message
(there is no local substitution).

.. code-block:: python

    query = gql(
        """
        query getContinentName ($code: ID!) {
          continent (code: $code) {
            name
          }
        }
    """
    )

    query.variable_values = {"code": "EU"}

    # Get name of continent with code "EU"
    result = client.execute(query)
    print(result)

    query.variable_values = {"code": "AF"}

    # Get name of continent with code "AF"
    result = client.execute(query)
    print(result)
