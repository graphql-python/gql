Error Handing
=============

Local errors
------------

If gql detects locally that something does not correspond to the GraphQL specification,
then gql may raise a **GraphQLError** from graphql-core.

This may happen for example:

- if your query is not valid
- if your query does not correspond to your schema
- if the result received from the backend does not correspond to the schema
  if :code:`parse_results` is set to True

Transport errors
----------------

If an error happens with the transport, then gql may raise a
:class:`TransportError <gql.transport.exceptions.TransportError>`

Here are the possible Transport Errors:

- :class:`TransportProtocolError <gql.transport.exceptions.TransportProtocolError>`:
  Should never happen if the backend is a correctly configured GraphQL server.
  It means that the answer received from the server does not correspond
  to the transport protocol.

- :class:`TransportServerError <gql.transport.exceptions.TransportServerError>`:
  There was an error communicating with the server. If this error is received,
  then the connection with the server will be closed. This may happen if the server
  returned a 404 http header for example.
  The http error code is available in the exception :code:`code` attribute.

- :class:`TransportQueryError <gql.transport.exceptions.TransportQueryError>`:
  There was a specific error returned from the server for your query.
  The message you receive in this error has been created by the backend, not gql!
  In that case, the connection to the server is still available and you are
  free to try to send other queries using the same connection.
  The message of the exception contains the first error returned by the backend.
  All the errors messages are available in the exception :code:`errors` attribute.

  If the error message begins with :code:`Error while fetching schema:`, it means
  that gql was not able to get the schema from the backend.
  If you don't need the schema, you can try to create the client with
  :code:`fetch_schema_from_transport=False`

- :class:`TransportClosed <gql.transport.exceptions.TransportClosed>`:
  This exception is generated when the client is trying to use the transport
  while the transport was previously closed.

- :class:`TransportAlreadyConnected <gql.transport.exceptions.TransportAlreadyConnected>`:
  Exception generated when the client is trying to connect to the transport
  while the transport is already connected.

HTTP
^^^^

For HTTP transports, we should get a json response which contain
:code:`data` or :code:`errors` fields.
If that is not the case, then the returned error depends whether the http return code
is below 400 or not.

- json response:
    - with data or errors keys:
        - no errors key -> no exception
        - errors key -> raise **TransportQueryError**
    - no data or errors keys:
        - http code < 400:
          raise **TransportProtocolError**
        - http code >= 400:
          raise **TransportServerError**
- not a json response:
    - http code < 400:
      raise **TransportProtocolError**
    - http code >= 400:
      raise **TransportServerError**
