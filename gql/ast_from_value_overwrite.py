"""

NOTE
THIS FILE IS A COPY PASTE OF graphql-core utilities/ast_from_value.py file

but with a possibility to overwrite the response
at any level of the recursive function.

"""
import re
from math import isfinite
from typing import Any, Iterable, Mapping, Optional, cast

from graphql import (
    BooleanValueNode,
    EnumValueNode,
    FloatValueNode,
    GraphQLID,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLList,
    GraphQLNonNull,
    IntValueNode,
    ListValueNode,
    NameNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    StringValueNode,
    ValueNode,
    is_enum_type,
    is_input_object_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
)
from graphql.pyutils import FrozenList, Undefined, inspect

__all__ = ["ast_from_value_overwrite"]

_re_integer_string = re.compile("^-?(?:0|[1-9][0-9]*)$")


def ast_from_value_overwrite(
    value: Any, type_: GraphQLInputType, overwrite=None
) -> Optional[ValueNode]:
    """
    THIS FILE IS A COPY PASTE OF graphql-core utilities/ast_from_value.py file

    but with a possibility to overwrite the response
    at any level of the recursive function.

    Produce a GraphQL Value AST given a Python object.

    This function will match Python/JSON values to GraphQL AST schema format by using
    the suggested GraphQLInputType. For example::

        ast_from_value('value', GraphQLString)

    A GraphQL type must be provided, which will be used to interpret different Python
    values.

    ================ =======================
       JSON Value         GraphQL Value
    ================ =======================
       Object          Input Object
       Array           List
       Boolean         Boolean
       String          String / Enum Value
       Number          Int / Float
       Mixed           Enum Value
       null            NullValue
    ================ =======================

    """
    if is_non_null_type(type_):
        type_ = cast(GraphQLNonNull, type_)
        ast_value = ast_from_value_overwrite(value, type_.of_type, overwrite)
        if isinstance(ast_value, NullValueNode):
            return None
        return ast_value

    # Overwrite the value using the provided function for custom cases
    if overwrite is not None:
        overwritten_ast = overwrite(value, type_)

        if overwritten_ast is not None:
            return overwritten_ast

    # only explicit None, not Undefined or NaN
    if value is None:
        return NullValueNode()

    # undefined
    if value is Undefined:
        return None

    # Convert Python list to GraphQL list. If the GraphQLType is a list, but the value
    # is not a list, convert the value using the list's item type.
    if is_list_type(type_):
        type_ = cast(GraphQLList, type_)
        item_type = type_.of_type
        if isinstance(value, Iterable) and not isinstance(value, str):
            maybe_value_nodes = (
                ast_from_value_overwrite(item, item_type, overwrite) for item in value
            )
            value_nodes = filter(None, maybe_value_nodes)
            return ListValueNode(values=FrozenList(value_nodes))
        return ast_from_value_overwrite(value, item_type, overwrite)

    # Populate the fields of the input object by creating ASTs from each value in the
    # Python dict according to the fields in the input type.
    if is_input_object_type(type_):
        if value is None or not isinstance(value, Mapping):
            return None
        type_ = cast(GraphQLInputObjectType, type_)
        field_items = (
            (
                field_name,
                ast_from_value_overwrite(value[field_name], field.type, overwrite),
            )
            for field_name, field in type_.fields.items()
            if field_name in value
        )
        field_nodes = (
            ObjectFieldNode(name=NameNode(value=field_name), value=field_value)
            for field_name, field_value in field_items
            if field_value
        )
        return ObjectValueNode(fields=FrozenList(field_nodes))

    if is_leaf_type(type_):
        # Since value is an internally represented value, it must be serialized to an
        # externally represented value before converting into an AST.
        serialized = type_.serialize(value)  # type: ignore
        if serialized is None or serialized is Undefined:
            return None

        # Others serialize based on their corresponding Python scalar types.
        if isinstance(serialized, bool):
            return BooleanValueNode(value=serialized)

        # Python ints and floats correspond nicely to Int and Float values.
        if isinstance(serialized, int):
            return IntValueNode(value=f"{serialized:d}")
        if isinstance(serialized, float) and isfinite(serialized):
            return FloatValueNode(value=f"{serialized:g}")

        if isinstance(serialized, str):
            # Enum types use Enum literals.
            if is_enum_type(type_):
                return EnumValueNode(value=serialized)

            # ID types can use Int literals.
            if type_ is GraphQLID and _re_integer_string.match(serialized):
                return IntValueNode(value=serialized)

            return StringValueNode(value=serialized)

        raise TypeError(f"Cannot convert value to AST: {inspect(serialized)}.")

    # Not reachable. All possible input types have been considered.
    raise TypeError(f"Unexpected input type: {inspect(type_)}.")
