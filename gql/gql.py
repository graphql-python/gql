from graphql import Source, parse


def gql(request_string):
    if not isinstance(request_string, str):
        raise Exception(f'Received incompatible request "{request_string}".')
    source = Source(request_string, "GraphQL request")
    return parse(source)
