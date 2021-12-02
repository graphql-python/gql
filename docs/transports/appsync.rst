.. _appsync_transport:

AppSyncWebsocketsTransport
==========================

AWS AppSync allows you to execute GraphQL subscriptions on its realtime GraphQL endpoint.

See `Building a real-time websocket client`_ for an explanation.

GQL provides the :code:`AppSyncWebsocketsTransport` transport which implements this
for you to allow you to execute subscriptions.

.. note::
    It is only possible to execute subscriptions with this transport

How to use it:

 * choose one :ref:`authentication method <appsync_authentication_methods>` (API key, IAM, Cognito user pools or OIDC)
 * instantiate a :code:`AppSyncWebsocketsTransport` with your GraphQL endpoint as url and your auth method

.. note::
    It is also possible to instantiate the transport without an auth argument. In that case,
    gql will use by default the :class:`IAM auth <gql.transport.appsync.AppSyncIAMAuthorization>`
    which will try to authenticate with environment variables or from your aws credentials file.

Full example with API key authentication from environment variables:

.. literalinclude:: ../code_examples/aws_api_key_subscription.py

Reference: :class:`gql.transport.appsync.AppSyncWebsocketsTransport`


.. _appsync_authentication_methods:

Authentication methods
----------------------

API key
^^^^^^^

Reference: :class:`gql.transport.appsync.AppSyncApiKeyAuthorization`

IAM
^^^

Reference: :class:`gql.transport.appsync.AppSyncIAMAuthorization`

Amazon Cognito user pools
^^^^^^^^^^^^^^^^^^^^^^^^^

Reference: :class:`gql.transport.appsync.AppSyncOIDCAuthorization`

OpenID Connect (OIDC)
^^^^^^^^^^^^^^^^^^^^^

Reference: :class:`gql.transport.appsync.AppSyncCognitoUserPoolAuthorization`

.. _Building a real-time websocket client: https://docs.aws.amazon.com/appsync/latest/devguide/real-time-websocket-client.html
