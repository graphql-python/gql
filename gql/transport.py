from graphql.execution import execute


class LocalSchemaTransport(object):
    def __init__(self, schema):
        self.schema = schema

    def execute(self, document, *args, **kwargs):
        return execute(
            self.schema,
            document,
            *args,
            **kwargs
        )


class HTTPTransport(object):
    pass

class RequestsTransport(object):
    pass
