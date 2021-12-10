.. _appsync_transport:

AppSyncWebsocketsTransport
==========================

AWS AppSync allows you to execute GraphQL subscriptions on its realtime GraphQL endpoint.

See `Building a real-time websocket client`_ for an explanation.

GQL provides the :code:`AppSyncWebsocketsTransport` transport which implements this
for you to allow you to execute subscriptions.

.. note::
    It is only possible to execute subscriptions with this transport.
    For queries or mutations, See :ref:`AppSync GraphQL Queries and mutations <appsync_http>`

How to use it:

 * choose one :ref:`authentication method <appsync_authentication_methods>` (API key, IAM, Cognito user pools or OIDC)
 * instantiate a :code:`AppSyncWebsocketsTransport` with your GraphQL endpoint as url and your auth method

.. note::
    It is also possible to instantiate the transport without an auth argument. In that case,
    gql will use by default the :class:`IAM auth <gql.transport.appsync_auth.AppSyncIAMAuthentication>`
    which will try to authenticate with environment variables or from your aws credentials file.

.. note::
    All the examples in this documentation are based on the sample app created
    by following `this AWS blog post`_

Full example with API key authentication from environment variables:

.. literalinclude:: ../code_examples/appsync/subscription_api_key.py

Reference: :class:`gql.transport.appsync_websockets.AppSyncWebsocketsTransport`

.. _Building a real-time websocket client: https://docs.aws.amazon.com/appsync/latest/devguide/real-time-websocket-client.html
.. _this AWS blog post: https://aws.amazon.com/fr/blogs/mobile/appsync-realtime/


.. _appsync_authentication_methods:

Authentication methods
----------------------

.. _appsync_api_key_auth:

API key
^^^^^^^

Use the :code:`AppSyncApiKeyAuthentication` class to provide your API key:

.. code-block:: python

    auth = AppSyncApiKeyAuthentication(
        host="XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com",
        api_key="YOUR_API_KEY",
    )

    transport = AppSyncWebsocketsTransport(
        url="https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql",
        auth=auth,
    )

Reference: :class:`gql.transport.appsync_auth.AppSyncApiKeyAuthentication`

.. _appsync_iam_auth:

IAM
^^^

For the IAM authentication, you can simply create your transport without
an auth argument.

The region name will be autodetected from the url or from your AWS configuration
(:code:`.aws/config`) or the environment variable:

- AWS_DEFAULT_REGION

The credentials will be detected from your AWS configuration file
(:code:`.aws/credentials`) or from the environment variables:

- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_SESSION_TOKEN (optional)

.. code-block:: python

    transport = AppSyncWebsocketsTransport(
        url="https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql",
    )

OR You can also provide the credentials manually by creating the
:code:`AppSyncIAMAuthentication` class yourself:

.. code-block:: python

    from botocore.credentials import Credentials

    credentials = Credentials(
        access_key = os.environ.get("AWS_ACCESS_KEY_ID"),
        secret_key= os.environ.get("AWS_SECRET_ACCESS_KEY"),
        token=os.environ.get("AWS_SESSION_TOKEN", None),   # Optional
    )

    auth = AppSyncIAMAuthentication(
        host="XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com",
        credentials=credentials,
        region_name="your region"
    )

    transport = AppSyncWebsocketsTransport(
        url="https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql",
        auth=auth,
    )

Reference: :class:`gql.transport.appsync_auth.AppSyncIAMAuthentication`

.. _appsync_jwt_auth:

Json Web Tokens (jwt)
^^^^^^^^^^^^^^^^^^^^^

AWS provides json web tokens (jwt) for the authentication methods:

- Amazon Cognito user pools
- OpenID Connect (OIDC)

For these authentication methods, you can use the :code:`AppSyncJWTAuthentication` class:

.. code-block:: python

    auth = AppSyncJWTAuthentication(
        host="XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com",
        jwt="YOUR_JWT_STRING",
    )

    transport = AppSyncWebsocketsTransport(
        url="https://XXXXXXXXXXXXXXXXXXXXXXXXXX.appsync-api.REGION.amazonaws.com/graphql",
        auth=auth,
    )

Reference: :class:`gql.transport.appsync_auth.AppSyncJWTAuthentication`

.. _appsync_http:

AppSync GraphQL Queries and mutations
-------------------------------------

Queries and mutations are not allowed on the realtime websockets endpoint.
But you can use the :ref:`AIOHTTPTransport <aiohttp_transport>` to create
a normal http session and reuse the authentication classes to create the headers for you.

Full example with API key authentication from environment variables:

.. literalinclude:: ../code_examples/appsync/mutation_api_key.py

From the command line
---------------------

Using :ref:`gql-cli <gql_cli>`, it is possible to execute GraphQL queries and subscriptions
from the command line on an AppSync endpoint.

- For queries and mutations, use the :code:`--transport appsync_http` argument::

    # Put the request in a file
    $ echo 'mutation createMessage($message: String!) {
      createMessage(input: {message: $message}) {
        id
        message
        createdAt
      }
    }' > mutation.graphql

    # Execute the request using gql-cli with --transport appsync_http
    $ cat mutation.graphql | gql-cli $AWS_GRAPHQL_API_ENDPOINT --transport appsync_http -V message:"Hello world!"

- For subscriptions, use the :code:`--transport appsync_websockets` argument::

    echo "subscription{onCreateMessage{message}}" | gql-cli $AWS_GRAPHQL_API_ENDPOINT --transport appsync_websockets

- You can also get the full GraphQL schema from the backend from introspection::

    $ gql-cli $AWS_GRAPHQL_API_ENDPOINT --transport appsync_http --print-schema > schema.graphql
