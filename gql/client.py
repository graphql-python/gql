from graphql import parse, introspection_query, build_ast_schema, build_client_schema
from graphql.validation import validate

from .transport.local_schema import LocalSchemaTransport


class Client(object):

    def __init__(self, schema=None, introspection=None, type_def=None, transport=None,
                 fetch_schema_from_transport=False):
        assert not(type_def and introspection), 'Cant provide introspection type definition at the same time'
        if transport and fetch_schema_from_transport:
            assert not schema, 'Cant fetch the schema from transport if is already provided'
            introspection = transport.execute(parse(introspection_query)).data
        if introspection:
            assert not schema, 'Cant provide introspection and schema at the same time'
            schema = build_client_schema(introspection)
        elif type_def:
            assert not schema, 'Cant provide Type definition and schema at the same time'
            type_def_ast = parse(type_def)
            schema = build_ast_schema(type_def_ast)
        elif schema and not transport:
            transport = LocalSchemaTransport(schema)

        self.schema = schema
        self.introspection = introspection
        self.transport = transport

    def validate(self, document):
        if not self.schema:
            raise Exception("Cannot validate locally the document, you need to pass a schema.")
        validation_errors = validate(self.schema, document)
        if validation_errors:
            raise validation_errors[0]

    def execute(self, document, *args, **kwargs):
        if self.schema:
            self.validate(document)
        result = self.transport.execute(document, *args, **kwargs)
        if result.errors:
            raise result.errors[0]
        return result.data
