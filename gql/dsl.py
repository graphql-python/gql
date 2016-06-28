import collections
import decimal
from functools import partial

import six
from graphql.language import ast
from graphql.language.printer import print_ast
from graphql.type import (GraphQLField, GraphQLFieldDefinition, GraphQLList,
                          GraphQLNonNull, GraphQLEnumType)


def selections(*fields):
    for _field in fields:
        yield field(_field).ast


def get_ast_value(value):
    if isinstance(value, ast.Node):
        return value
    if isinstance(value, six.string_types):
        return ast.StringValue(value=value)
    elif isinstance(value, bool):
        return ast.BooleanValue(value=value)
    elif isinstance(value, (float, decimal.Decimal)):
        return ast.FloatValue(value=value)
    elif isinstance(value, int):
        return ast.IntValue(value=value)
    return None


class DSLField(object):

    def __init__(self, field):
        self.field = field
        self.ast_field = ast.Field(name=ast.Name(value=field.name), arguments=[])
        self.selection_set = None

    def get(self, *fields):
        if not self.ast_field.selection_set:
            self.ast_field.selection_set = ast.SelectionSet(selections=[])
        self.ast_field.selection_set.selections.extend(selections(*fields))
        return self

    def alias(self, alias):
        self.ast_field.alias = ast.Name(value=alias)
        return self

    def get_field_args(self):
        if isinstance(self.field, GraphQLFieldDefinition):
            # The args will be an array
            return {
                arg.name: arg for arg in self.field.args
            }
        return self.field.args

    def args(self, **args):
        for name, value in args.items():
            arg = self.get_field_args().get(name)
            arg_type_serializer = get_arg_serializer(arg.type)
            value = arg_type_serializer(value)
            self.ast_field.arguments.append(
                ast.Argument(
                    name=ast.Name(value=name),
                    value=get_ast_value(value)
                )
            )
        return self

    @property
    def ast(self):
        return self.ast_field

    def __str__(self):
        return print_ast(self.ast_field)


def field(field, **args):
    if isinstance(field, (GraphQLField, GraphQLFieldDefinition)):
        return DSLField(field).args(**args)
    elif isinstance(field, DSLField):
        return field

    raise Exception('Received incompatible query field: "{}".'.format(field))


def query(*fields):
    return ast.Document(
        definitions=[ast.OperationDefinition(
            operation='query',
            selection_set=ast.SelectionSet(
                selections=list(selections(*fields))
            )
        )]
    )


def serialize_list(serializer, values):
    assert isinstance(values, collections.Iterable), 'Expected iterable, received "{}"'.format(repr(values))
    return [serializer(v) for v in values]


def get_arg_serializer(arg_type):
    if isinstance(arg_type, GraphQLNonNull):
        return get_arg_serializer(arg_type.of_type)
    if isinstance(arg_type, GraphQLList):
        inner_serializer = get_arg_serializer(arg_type.of_type)
        return partial(serialize_list, inner_serializer)
    if isinstance(arg_type, GraphQLEnumType):
        return lambda value: ast.EnumValue(value=arg_type.serialize(value))
    return arg_type.serialize


def var(name):
    return ast.Variable(name=name)
