from collections.abc import Iterable
from functools import partial

from graphql import (
    ArgumentNode,
    DocumentNode,
    EnumValueNode,
    FieldNode,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    ListValueNode,
    NameNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    ast_from_value,
    print_ast,
)
from graphql.pyutils import FrozenList

from .utils import to_camel_case


class DSLSchema(object):
    def __init__(self, client):
        self.client = client

    @property
    def schema(self):
        return self.client.schema

    def __getattr__(self, name):
        type_def = self.schema.get_type(name)
        return DSLType(type_def)

    def query(self, *args, **kwargs):
        return self.execute(query(*args, **kwargs))

    def mutate(self, *args, **kwargs):
        return self.query(*args, operation="mutation", **kwargs)

    def execute(self, document):
        return self.client.execute(document)


class DSLType(object):
    def __init__(self, type_):
        self.type = type_

    def __getattr__(self, name):
        formatted_name, field_def = self.get_field(name)
        return DSLField(formatted_name, field_def)

    def get_field(self, name):
        camel_cased_name = to_camel_case(name)

        if name in self.type.fields:
            return name, self.type.fields[name]

        if camel_cased_name in self.type.fields:
            return camel_cased_name, self.type.fields[camel_cased_name]

        raise KeyError(f"Field {name} does not exist in type {self.type.name}.")


def selections(*fields):
    for _field in fields:
        yield selection_field(_field).ast


class DSLField(object):
    def __init__(self, name, field):
        self.field = field
        self.ast_field = FieldNode(name=NameNode(value=name), arguments=FrozenList())
        self.selection_set = None

    def select(self, *fields):
        selection_set = self.ast_field.selection_set
        added_selections = selections(*fields)
        if selection_set:
            selection_set.selections = FrozenList(
                selection_set.selections + list(added_selections)
            )
        else:
            self.ast_field.selection_set = SelectionSetNode(
                selections=FrozenList(added_selections)
            )
        return self

    def __call__(self, **kwargs):
        return self.args(**kwargs)

    def alias(self, alias):
        self.ast_field.alias = NameNode(value=alias)
        return self

    def args(self, **kwargs):
        added_args = []
        for name, value in kwargs.items():
            arg = self.field.args.get(name)
            if not arg:
                raise KeyError(f"Argument {name} does not exist in {self.field}.")
            arg_type_serializer = get_arg_serializer(arg.type, known_serializers=dict())
            serialized_value = arg_type_serializer(value)
            added_args.append(
                ArgumentNode(name=NameNode(value=name), value=serialized_value)
            )
        ast_field = self.ast_field
        ast_field.arguments = FrozenList(ast_field.arguments + added_args)
        return self

    @property
    def ast(self):
        return self.ast_field

    def __str__(self):
        return print_ast(self.ast_field)


def selection_field(field):
    if isinstance(field, DSLField):
        return field

    raise TypeError(f'Received incompatible query field: "{field}".')


def query(*fields, **kwargs):
    if "operation" not in kwargs:
        kwargs["operation"] = "query"
    return DocumentNode(
        definitions=[
            OperationDefinitionNode(
                operation=OperationType(kwargs["operation"]),
                selection_set=SelectionSetNode(
                    selections=FrozenList(selections(*fields))
                ),
            )
        ]
    )


def serialize_list(serializer, list_values):
    assert isinstance(
        list_values, Iterable
    ), f'Expected iterable, received "{list_values!r}".'
    return ListValueNode(values=FrozenList(serializer(v) for v in list_values))


def get_arg_serializer(arg_type, known_serializers):
    if isinstance(arg_type, GraphQLNonNull):
        return get_arg_serializer(arg_type.of_type, known_serializers)
    if isinstance(arg_type, GraphQLInputField):
        return get_arg_serializer(arg_type.type, known_serializers)
    if isinstance(arg_type, GraphQLInputObjectType):
        if arg_type in known_serializers:
            return known_serializers[arg_type]
        known_serializers[arg_type] = None
        serializers = {
            k: get_arg_serializer(v, known_serializers)
            for k, v in arg_type.fields.items()
        }
        known_serializers[arg_type] = lambda value: ObjectValueNode(
            fields=FrozenList(
                ObjectFieldNode(name=NameNode(value=k), value=serializers[k](v))
                for k, v in value.items()
            )
        )
        return known_serializers[arg_type]
    if isinstance(arg_type, GraphQLList):
        inner_serializer = get_arg_serializer(arg_type.of_type, known_serializers)
        return partial(serialize_list, inner_serializer)
    if isinstance(arg_type, GraphQLEnumType):
        return lambda value: EnumValueNode(value=arg_type.serialize(value))
    return lambda value: ast_from_value(arg_type.serialize(value), arg_type)
