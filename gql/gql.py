from graphql import DocumentNode, Source, parse


def gql(request_string: str) -> DocumentNode:
    """Given a String containing a GraphQL request, parse it into a Document.

    :param request_string: the GraphQL request as a String
    :type request_string: str
    :return: a Document which can be later executed or subscribed by a
        :class:`Client <gql.client.Client>`, by an
        :class:`async session <gql.client.AsyncClientSession>` or by a
        :class:`sync session <gql.client.SyncClientSession>`

    :raises GraphQLError: if a syntax error is encountered.
    """
    source = Source(request_string, "GraphQL request")
    return parse(source)
