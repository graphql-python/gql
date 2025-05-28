from .graphql_request import GraphQLRequest


def gql(request_string: str) -> GraphQLRequest:
    """Given a string containing a GraphQL request,
       parse it into a Document and put it into a GraphQLRequest object.

    :param request_string: the GraphQL request as a String
    :return: a :class:`GraphQLRequest <gql.GraphQLRequest>`
             which can be later executed or subscribed by a
             :class:`Client <gql.client.Client>`, by an
             :class:`async session <gql.client.AsyncClientSession>` or by a
             :class:`sync session <gql.client.SyncClientSession>`
    :raises graphql.error.GraphQLError: if a syntax error is encountered.
    """
    return GraphQLRequest(request_string)
