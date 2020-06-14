from graphql import DocumentNode, Source, parse


def gql(request_string: str) -> DocumentNode:
    source = Source(request_string, "GraphQL request")
    return parse(source)
