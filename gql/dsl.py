import logging
from abc import ABC
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union, cast

from graphql import (
    ArgumentNode,
    DocumentNode,
    FieldNode,
    GraphQLArgument,
    GraphQLField,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLWrappingType,
    ListTypeNode,
    ListValueNode,
    NamedTypeNode,
    NameNode,
    NonNullTypeNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    TypeNode,
    Undefined,
    ValueNode,
    VariableDefinitionNode,
    VariableNode,
    assert_named_type,
    is_input_object_type,
    is_list_type,
    is_non_null_type,
    is_wrapping_type,
    print_ast,
)
from graphql.pyutils import FrozenList
from graphql.utilities import ast_from_value as default_ast_from_value

from .utils import to_camel_case

log = logging.getLogger(__name__)


def ast_from_value(value: Any, type_: GraphQLInputType) -> Optional[ValueNode]:
    """
    This is a partial copy paste of the ast_from_value function in
    graphql-core utilities/ast_from_value.py

    Overwrite the if blocks that use recursion and add a new case to return a
    VariableNode when value is a DSLVariable

    Produce a GraphQL Value AST given a Python object.
    """
    if isinstance(value, DSLVariable):
        return value.set_type(type_).ast_variable

    if is_non_null_type(type_):
        type_ = cast(GraphQLNonNull, type_)
        ast_value = ast_from_value(value, type_.of_type)
        if isinstance(ast_value, NullValueNode):
            return None
        return ast_value

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
            maybe_value_nodes = (ast_from_value(item, item_type) for item in value)
            value_nodes = filter(None, maybe_value_nodes)
            return ListValueNode(values=FrozenList(value_nodes))
        return ast_from_value(value, item_type)

    # Populate the fields of the input object by creating ASTs from each value in the
    # Python dict according to the fields in the input type.
    if is_input_object_type(type_):
        if value is None or not isinstance(value, Mapping):
            return None
        type_ = cast(GraphQLInputObjectType, type_)
        field_items = (
            (field_name, ast_from_value(value[field_name], field.type))
            for field_name, field in type_.fields.items()
            if field_name in value
        )
        field_nodes = (
            ObjectFieldNode(name=NameNode(value=field_name), value=field_value)
            for field_name, field_value in field_items
            if field_value
        )
        return ObjectValueNode(fields=FrozenList(field_nodes))

    return default_ast_from_value(value, type_)


def dsl_gql(
    *operations: "DSLOperation", **operations_with_name: "DSLOperation"
) -> DocumentNode:
    r"""Given arguments instances of :class:`DSLOperation`
    containing GraphQL operations,
    generate a Document which can be executed later in a
    gql client or a gql session.

    Similar to the :func:`gql.gql` function but instead of parsing a python
    string to describe the request, we are using operations which have been generated
    dynamically using instances of :class:`DSLField`, generated
    by instances of :class:`DSLType` which themselves originated from
    a :class:`DSLSchema` class.

    :param \*operations: the GraphQL operations
    :type \*operations: DSLOperation (DSLQuery, DSLMutation, DSLSubscription)
    :param \**operations_with_name: the GraphQL operations with an operation name
    :type \**operations_with_name: DSLOperation (DSLQuery, DSLMutation, DSLSubscription)

    :return: a Document which can be later executed or subscribed by a
        :class:`Client <gql.client.Client>`, by an
        :class:`async session <gql.client.AsyncClientSession>` or by a
        :class:`sync session <gql.client.SyncClientSession>`

    :raises TypeError: if an argument is not an instance of :class:`DSLOperation`
    """

    # Concatenate operations without and with name
    all_operations: Tuple["DSLOperation", ...] = (
        *operations,
        *(operation for operation in operations_with_name.values()),
    )

    # Set the operation name
    for name, operation in operations_with_name.items():
        operation.name = name

    # Check the type
    for operation in all_operations:
        if not isinstance(operation, DSLOperation):
            raise TypeError(
                "Operations should be instances of DSLOperation "
                "(DSLQuery, DSLMutation or DSLSubscription).\n"
                f"Received: {type(operation)}."
            )

    return DocumentNode(
        definitions=[
            OperationDefinitionNode(
                operation=OperationType(operation.operation_type),
                selection_set=operation.selection_set,
                variable_definitions=FrozenList(
                    operation.variable_definitions.get_ast_definitions()
                ),
                **({"name": NameNode(value=operation.name)} if operation.name else {}),
            )
            for operation in all_operations
        ]
    )


class DSLSchema:
    """The DSLSchema is the root of the DSL code.

    Attributes of the DSLSchema class are generated automatically
    with the `__getattr__` dunder method in order to generate
    instances of :class:`DSLType`
    """

    def __init__(self, schema: GraphQLSchema):
        """Initialize the DSLSchema with the given schema.

        :param schema: a GraphQL Schema provided locally or fetched using
                       an introspection query. Usually `client.schema`
        :type schema: GraphQLSchema

        :raises TypeError: if the argument is not an instance of :class:`GraphQLSchema`
        """

        if not isinstance(schema, GraphQLSchema):
            raise TypeError(
                f"DSLSchema needs a schema as parameter. Received: {type(schema)}"
            )

        self._schema: GraphQLSchema = schema

    def __getattr__(self, name: str) -> "DSLType":

        type_def: Optional[GraphQLNamedType] = self._schema.get_type(name)

        if type_def is None:
            raise AttributeError(f"Type '{name}' not found in the schema!")

        assert isinstance(type_def, GraphQLObjectType) or isinstance(
            type_def, GraphQLInterfaceType
        )

        return DSLType(type_def)


class DSLOperation(ABC):
    """Interface for GraphQL operations.

    Inherited by
    :class:`DSLQuery <gql.dsl.DSLQuery>`,
    :class:`DSLMutation <gql.dsl.DSLMutation>` and
    :class:`DSLSubscription <gql.dsl.DSLSubscription>`
    """

    operation_type: OperationType

    def __init__(
        self, *fields: "DSLField", **fields_with_alias: "DSLField",
    ):
        r"""Given arguments of type :class:`DSLField` containing GraphQL requests,
        generate an operation which can be converted to a Document
        using the :func:`dsl_gql <gql.dsl.dsl_gql>`.

        The fields arguments should be fields of root GraphQL types
        (Query, Mutation or Subscription) and correspond to the
        operation_type of this operation.

        :param \*fields: root instances of the dynamically generated requests
        :type \*fields: DSLField
        :param \**fields_with_alias: root instances fields with alias as key
        :type \**fields_with_alias: DSLField

        :raises TypeError: if an argument is not an instance of :class:`DSLField`
        :raises AssertionError: if an argument is not a field which correspond
                                to the operation type
        """

        self.name: Optional[str] = None
        self.variable_definitions: DSLVariableDefinitions = DSLVariableDefinitions()

        # Concatenate fields without and with alias
        all_fields: Tuple["DSLField", ...] = DSLField.get_aliased_fields(
            fields, fields_with_alias
        )

        # Check that we receive only arguments of type DSLField
        # And that the root type correspond to the operation
        for field in all_fields:
            if not isinstance(field, DSLField):
                raise TypeError(
                    (
                        "fields must be instances of DSLField. "
                        f"Received type: {type(field)}"
                    )
                )
            assert field.type_name.upper() == self.operation_type.name, (
                f"Invalid root field for operation {self.operation_type.name}.\n"
                f"Received: {field.type_name}"
            )

        self.selection_set: SelectionSetNode = SelectionSetNode(
            selections=FrozenList(DSLField.get_ast_fields(all_fields))
        )


class DSLQuery(DSLOperation):
    operation_type = OperationType.QUERY


class DSLMutation(DSLOperation):
    operation_type = OperationType.MUTATION


class DSLSubscription(DSLOperation):
    operation_type = OperationType.SUBSCRIPTION


class DSLVariable:
    """The DSLVariable represents a single variable defined in a GraphQL operation

    Instances of this class are generated for you automatically as attributes
    of the :class:`DSLVariableDefinitions`

    The type of the variable is set by the :class:`DSLField` instance that receives it
    in the `args` method.
    """

    def __init__(self, name: str):
        self.type: Optional[TypeNode] = None
        self.name = name
        self.ast_variable = VariableNode(name=NameNode(value=self.name))

    def to_ast_type(
        self, type_: Union[GraphQLWrappingType, GraphQLNamedType]
    ) -> TypeNode:
        if is_wrapping_type(type_):
            if isinstance(type_, GraphQLList):
                return ListTypeNode(type=self.to_ast_type(type_.of_type))
            elif isinstance(type_, GraphQLNonNull):
                return NonNullTypeNode(type=self.to_ast_type(type_.of_type))

        type_ = assert_named_type(type_)
        return NamedTypeNode(name=NameNode(value=type_.name))

    def set_type(
        self, type_: Union[GraphQLWrappingType, GraphQLNamedType]
    ) -> "DSLVariable":
        self.type = self.to_ast_type(type_)
        return self


class DSLVariableDefinitions:
    """The DSLVariableDefinitions represents variable definitions in a GraphQL operation

    Instances of this class have to be created and set as the `variable_definitions`
    attribute of a DSLOperation instance

    Attributes of the DSLVariableDefinitions class are generated automatically
    with the `__getattr__` dunder method in order to generate
    instances of :class:`DSLVariable`, that can then be used as values in the
    `DSLField.args` method
    """

    def __init__(self):
        self.variables: Dict[str, DSLVariable] = {}

    def __getattr__(self, name: str) -> "DSLVariable":
        if name not in self.variables:
            self.variables[name] = DSLVariable(name)
        return self.variables[name]

    def get_ast_definitions(self) -> List[VariableDefinitionNode]:
        """
        :meta private:

        Return a list of VariableDefinitionNodes for each variable with a type
        """
        return [
            VariableDefinitionNode(
                type=var.type, variable=var.ast_variable, default_value=None,
            )
            for var in self.variables.values()
            if var.type is not None  # only variables used
        ]


class DSLType:
    """The DSLType represents a GraphQL type for the DSL code.

    It can be a root type (Query, Mutation or Subscription).
    Or it can be any other object type (Human in the StarWars schema).
    Or it can be an interface type (Character in the StarWars schema).

    Instances of this class are generated for you automatically as attributes
    of the :class:`DSLSchema`

    Attributes of the DSLType class are generated automatically
    with the `__getattr__` dunder method in order to generate
    instances of :class:`DSLField`
    """

    def __init__(self, graphql_type: Union[GraphQLObjectType, GraphQLInterfaceType]):
        """Initialize the DSLType with the GraphQL type.

        .. warning::
            Don't instantiate this class yourself.
            Use attributes of the :class:`DSLSchema` instead.

        :param graphql_type: the GraphQL type definition from the schema
        """
        self._type: Union[GraphQLObjectType, GraphQLInterfaceType] = graphql_type
        log.debug(f"Creating {self!r})")

    def __getattr__(self, name: str) -> "DSLField":
        camel_cased_name = to_camel_case(name)

        if name in self._type.fields:
            formatted_name = name
            field = self._type.fields[name]
        elif camel_cased_name in self._type.fields:
            formatted_name = camel_cased_name
            field = self._type.fields[camel_cased_name]
        else:
            raise AttributeError(
                f"Field {name} does not exist in type {self._type.name}."
            )

        return DSLField(formatted_name, self._type, field)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._type!r}>"


class DSLField:
    """The DSLField represents a GraphQL field for the DSL code.

    Instances of this class are generated for you automatically as attributes
    of the :class:`DSLType`

    If this field contains children fields, then you need to select which ones
    you want in the request using the :meth:`select <gql.dsl.DSLField.select>`
    method.
    """

    def __init__(
        self,
        name: str,
        graphql_type: Union[GraphQLObjectType, GraphQLInterfaceType],
        graphql_field: GraphQLField,
    ):
        """Initialize the DSLField.

        .. warning::
            Don't instantiate this class yourself.
            Use attributes of the :class:`DSLType` instead.

        :param name: the name of the field
        :param graphql_type: the GraphQL type definition from the schema
        :param graphql_field: the GraphQL field definition from the schema
        """
        self._type: Union[GraphQLObjectType, GraphQLInterfaceType] = graphql_type
        self.field: GraphQLField = graphql_field
        self.ast_field: FieldNode = FieldNode(
            name=NameNode(value=name), arguments=FrozenList()
        )
        log.debug(f"Creating {self!r}")

    @staticmethod
    def get_ast_fields(fields: Iterable["DSLField"]) -> List[FieldNode]:
        """
        :meta private:

        Equivalent to: :code:`[field.ast_field for field in fields]`
        But with a type check for each field in the list.

        :raises TypeError: if any of the provided fields are not instances
                           of the :class:`DSLField` class.
        """
        ast_fields = []
        for field in fields:
            if isinstance(field, DSLField):
                ast_fields.append(field.ast_field)
            else:
                raise TypeError(f'Received incompatible field: "{field}".')

        return ast_fields

    @staticmethod
    def get_aliased_fields(
        fields: Iterable["DSLField"], fields_with_alias: Dict[str, "DSLField"]
    ) -> Tuple["DSLField", ...]:
        """
        :meta private:

        Concatenate all the fields (with or without alias) in a Tuple.

        Set the requested alias for the fields with alias.
        """

        return (
            *fields,
            *(field.alias(alias) for alias, field in fields_with_alias.items()),
        )

    def select(
        self, *fields: "DSLField", **fields_with_alias: "DSLField"
    ) -> "DSLField":
        r"""Select the new children fields
        that we want to receive in the request.

        If used multiple times, we will add the new children fields
        to the existing children fields.

        :param \*fields: new children fields
        :type \*fields: DSLField
        :param \**fields_with_alias: new children fields with alias as key
        :type \**fields_with_alias: DSLField
        :return: itself

        :raises TypeError: if any of the provided fields are not instances
                           of the :class:`DSLField` class.
        """

        # Concatenate fields without and with alias
        added_fields: Tuple["DSLField", ...] = self.get_aliased_fields(
            fields, fields_with_alias
        )

        added_selections: List[FieldNode] = self.get_ast_fields(added_fields)

        current_selection_set: Optional[SelectionSetNode] = self.ast_field.selection_set

        if current_selection_set is None:
            self.ast_field.selection_set = SelectionSetNode(
                selections=FrozenList(added_selections)
            )
        else:
            current_selection_set.selections = FrozenList(
                current_selection_set.selections + added_selections
            )

        log.debug(f"Added fields: {fields} in {self!r}")

        return self

    def __call__(self, **kwargs) -> "DSLField":
        return self.args(**kwargs)

    def alias(self, alias: str) -> "DSLField":
        """Set an alias

        .. note::
            You can also pass the alias directly at the
            :meth:`select <gql.dsl.DSLField.select>` method.
            :code:`ds.Query.human.select(my_name=ds.Character.name)` is equivalent to:
            :code:`ds.Query.human.select(ds.Character.name.alias("my_name"))`

        :param alias: the alias
        :type alias: str
        :return: itself
        """

        self.ast_field.alias = NameNode(value=alias)
        return self

    def args(self, **kwargs) -> "DSLField":
        r"""Set the arguments of a field

        The arguments are parsed to be stored in the AST of this field.

        .. note::
            You can also call the field directly with your arguments.
            :code:`ds.Query.human(id=1000)` is equivalent to:
            :code:`ds.Query.human.args(id=1000)`

        :param \**kwargs: the arguments (keyword=value)
        :return: itself

        :raises KeyError: if any of the provided arguments does not exist
                          for this field.
        """

        assert self.ast_field.arguments is not None

        self.ast_field.arguments = FrozenList(
            self.ast_field.arguments
            + [
                ArgumentNode(
                    name=NameNode(value=name),
                    value=ast_from_value(value, self._get_argument(name).type),
                )
                for name, value in kwargs.items()
            ]
        )

        log.debug(f"Added arguments {kwargs} in field {self!r})")

        return self

    def _get_argument(self, name: str) -> GraphQLArgument:
        """Method used to return the GraphQLArgument definition
        of an argument from its name.

        :raises KeyError: if the provided argument does not exist
                          for this field.
        """
        arg = self.field.args.get(name)

        if arg is None:
            raise KeyError(f"Argument {name} does not exist in {self.field}.")

        return arg

    @property
    def type_name(self):
        """:meta private:"""
        return self._type.name

    def __str__(self) -> str:
        return print_ast(self.ast_field)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} {self._type.name}"
            f"::{self.ast_field.name.value}>"
        )
