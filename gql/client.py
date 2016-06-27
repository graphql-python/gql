from graphql.execution import execute
from graphql.validation import validate
from graphql.utils.build_client_schema import build_client_schema
from graphql.utils.build_ast_schema import build_ast_schema
from graphql import parse


class Client(object):
    def __init__(self, schema=None, introspection=None, type_def=None, transport=None):
        assert not(type_def and introspection), 'Cant provide introspection type definition at the same time'
        if introspection:
            assert not schema, 'Cant provide introspection and schema at the same time'
            schema = build_client_schema(introspection)
        elif type_def:
            assert not schema, 'Cant provide Type definition and schema at the same time'
            type_def_ast = parse(type_def)
            schema = build_ast_schema(type_def_ast)
        self.schema = schema
        self.introspection = introspection
        self.transport = transport

    def validate(self, document):
        if not self.schema:
            raise Exception("Cannot validate locally the document, you need to pass a schema.")
        validation_errors = validate(self.schema, document)
        if validation_errors:
            raise validation_errors[0]

    def execute(self, document):
        if self.schema:
            self.validate(document)
        result = execute(
            self.schema,
            document,
        )
        if result.errors:
            raise result.errors[0]
        return result.data
