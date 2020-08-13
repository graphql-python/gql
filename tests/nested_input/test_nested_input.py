from functools import partial

import pytest
from graphql import (
    EnumValueNode,
    GraphQLEnumType,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLList,
    GraphQLNonNull,
    NameNode,
    ObjectFieldNode,
    ObjectValueNode,
    ast_from_value,
)
from graphql.pyutils import FrozenList

import gql.dsl as dsl
from gql import Client
from gql.dsl import DSLSchema, serialize_list
from tests.nested_input.schema import NestedInputSchema

# back up the new func
new_get_arg_serializer = dsl.get_arg_serializer


def old_get_arg_serializer(arg_type, known_serializers=None):
    if isinstance(arg_type, GraphQLNonNull):
        return old_get_arg_serializer(arg_type.of_type)
    if isinstance(arg_type, GraphQLInputField):
        return old_get_arg_serializer(arg_type.type)
    if isinstance(arg_type, GraphQLInputObjectType):
        serializers = {k: old_get_arg_serializer(v) for k, v in arg_type.fields.items()}
        return lambda value: ObjectValueNode(
            fields=FrozenList(
                ObjectFieldNode(name=NameNode(value=k), value=serializers[k](v))
                for k, v in value.items()
            )
        )
    if isinstance(arg_type, GraphQLList):
        inner_serializer = old_get_arg_serializer(arg_type.of_type)
        return partial(serialize_list, inner_serializer)
    if isinstance(arg_type, GraphQLEnumType):
        return lambda value: EnumValueNode(value=arg_type.serialize(value))
    return lambda value: ast_from_value(arg_type.serialize(value), arg_type)


@pytest.fixture
def ds():
    client = Client(schema=NestedInputSchema)
    ds = DSLSchema(client)
    return ds


def test_nested_input_with_old_get_arg_serializer(ds):
    dsl.get_arg_serializer = old_get_arg_serializer
    with pytest.raises(RecursionError, match="maximum recursion depth exceeded"):
        ds.query(ds.Query.foo.args(nested={"foo": 1}))


def test_nested_input_with_new_get_arg_serializer(ds):
    dsl.get_arg_serializer = new_get_arg_serializer
    assert ds.query(ds.Query.foo.args(nested={"foo": 1})) == {"foo": 1}
