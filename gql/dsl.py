from collections.abc import Iterable
from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from graphql import (
    ArgumentNode,
    DocumentNode,
    EnumValueNode,
    FieldNode,
    GraphQLEnumType,
    GraphQLField,
    GraphQLInputField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
    ListValueNode,
    NameNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    ValueNode,
    ast_from_value,
    print_ast,
)
from graphql.pyutils import FrozenList

from .utils import to_camel_case

GraphQLTypeWithFields = Union[GraphQLObjectType, GraphQLInterfaceType]
Serializer = Callable[[Any], Optional[ValueNode]]


class DSLSchema:
    def __init__(self, schema: GraphQLSchema):

        assert isinstance(
            schema, GraphQLSchema
        ), "DSLSchema needs a schema as parameter"

        self._schema: GraphQLSchema = schema

    def __getattr__(self, name: str) -> "DSLType":

        type_def: Optional[GraphQLNamedType] = self._schema.get_type(name)

        assert isinstance(type_def, GraphQLObjectType) or isinstance(
            type_def, GraphQLInterfaceType
        )

        return DSLType(type_def)

    def gql(self, *fields: "DSLField", operation: str = "query") -> DocumentNode:

        return DocumentNode(
            definitions=[
                OperationDefinitionNode(
                    operation=OperationType(operation),
                    selection_set=SelectionSetNode(
                        selections=FrozenList(DSLField.get_ast_fields(fields))
                    ),
                )
            ]
        )


class DSLType:
    def __init__(self, type_: GraphQLTypeWithFields):
        self._type: GraphQLTypeWithFields = type_

    def __getattr__(self, name: str) -> "DSLField":
        formatted_name, field_def = self._get_field(name)
        return DSLField(formatted_name, field_def)

    def _get_field(self, name: str) -> Tuple[str, GraphQLField]:
        camel_cased_name = to_camel_case(name)

        if name in self._type.fields:
            return name, self._type.fields[name]

        if camel_cased_name in self._type.fields:
            return camel_cased_name, self._type.fields[camel_cased_name]

        raise KeyError(f"Field {name} does not exist in type {self._type.name}.")


class DSLField:

    # Definition of field from the schema
    field: GraphQLField

    # Current selection in the query
    ast_field: FieldNode

    # Known serializers
    known_serializers: Dict[GraphQLInputType, Optional[Serializer]]

    def __init__(self, name: str, field: GraphQLField):
        self.field = field
        self.ast_field = FieldNode(name=NameNode(value=name), arguments=FrozenList())
        self.known_serializers = dict()

    @staticmethod
    def get_ast_fields(fields: Iterable) -> List[FieldNode]:
        """
        Equivalent to: [field.ast_field for field in fields]
        But with a type check for each field in the list

        Raises a TypeError if any of the provided fields are not of the DSLField type
        """
        ast_fields = []
        for field in fields:
            if isinstance(field, DSLField):
                ast_fields.append(field.ast_field)
            else:
                raise TypeError(f'Received incompatible field: "{field}".')

        return ast_fields

    def select(self, *fields: "DSLField") -> "DSLField":

        added_selections: List[FieldNode] = self.get_ast_fields(fields)

        current_selection_set: Optional[SelectionSetNode] = self.ast_field.selection_set

        if current_selection_set is None:
            self.ast_field.selection_set = SelectionSetNode(
                selections=FrozenList(added_selections)
            )
        else:
            current_selection_set.selections = FrozenList(
                current_selection_set.selections + added_selections
            )

        return self

    def __call__(self, **kwargs) -> "DSLField":
        return self.args(**kwargs)

    def alias(self, alias: str) -> "DSLField":
        self.ast_field.alias = NameNode(value=alias)
        return self

    def args(self, **kwargs) -> "DSLField":
        added_args = []
        for name, value in kwargs.items():
            arg = self.field.args.get(name)
            if not arg:
                raise KeyError(f"Argument {name} does not exist in {self.field}.")
            arg_type_serializer = self._get_arg_serializer(arg.type)
            serialized_value = arg_type_serializer(value)
            added_args.append(
                ArgumentNode(name=NameNode(value=name), value=serialized_value)
            )
        self.ast_field.arguments = FrozenList(self.ast_field.arguments + added_args)
        return self

    def _get_arg_serializer(self, arg_type: GraphQLInputType,) -> Serializer:
        if isinstance(arg_type, GraphQLNonNull):
            return self._get_arg_serializer(arg_type.of_type)
        elif isinstance(arg_type, GraphQLInputField):
            return self._get_arg_serializer(arg_type.type)
        elif isinstance(arg_type, GraphQLInputObjectType):
            if arg_type in self.known_serializers:
                return cast(Serializer, self.known_serializers[arg_type])
            self.known_serializers[arg_type] = None
            serializers = {
                k: self._get_arg_serializer(v) for k, v in arg_type.fields.items()
            }
            self.known_serializers[arg_type] = lambda value: ObjectValueNode(
                fields=FrozenList(
                    ObjectFieldNode(name=NameNode(value=k), value=serializers[k](v))
                    for k, v in value.items()
                )
            )
            return cast(Serializer, self.known_serializers[arg_type])
        elif isinstance(arg_type, GraphQLList):
            inner_serializer = self._get_arg_serializer(arg_type.of_type)
            return lambda list_values: ListValueNode(
                values=FrozenList(inner_serializer(v) for v in list_values)
            )
        elif isinstance(arg_type, GraphQLEnumType):
            return lambda value: EnumValueNode(
                value=cast(GraphQLEnumType, arg_type).serialize(value)
            )

        return lambda value: ast_from_value(
            cast(GraphQLScalarType, arg_type).serialize(value), arg_type
        )

    def __str__(self) -> str:
        return print_ast(self.ast_field)
