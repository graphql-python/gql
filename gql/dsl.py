import logging
import re
from abc import ABC, abstractmethod
from math import isfinite
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union, cast

from graphql import (
    ArgumentNode,
    BooleanValueNode,
    DocumentNode,
    EnumValueNode,
    FieldNode,
    FloatValueNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    GraphQLArgument,
    GraphQLError,
    GraphQLField,
    GraphQLID,
    GraphQLInputObjectType,
    GraphQLInputType,
    GraphQLInterfaceType,
    GraphQLList,
    GraphQLNamedType,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLSchema,
    GraphQLWrappingType,
    InlineFragmentNode,
    IntValueNode,
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
    StringValueNode,
    TypeNode,
    Undefined,
    ValueNode,
    VariableDefinitionNode,
    VariableNode,
    assert_named_type,
    is_enum_type,
    is_input_object_type,
    is_leaf_type,
    is_list_type,
    is_non_null_type,
    is_wrapping_type,
    print_ast,
)
from graphql.pyutils import FrozenList, inspect

from .utils import to_camel_case

log = logging.getLogger(__name__)

_re_integer_string = re.compile("^-?(?:0|[1-9][0-9]*)$")


def ast_from_serialized_value_untyped(serialized: Any) -> Optional[ValueNode]:
    """Given a serialized value, try our best to produce an AST.

    Anything ressembling an array (instance of Mapping) will be converted
    to an ObjectFieldNode.

    Anything ressembling a list (instance of Iterable - except str)
    will be converted to a ListNode.

    In some cases, a custom scalar can be serialized differently in the query
    than in the variables. In that case, this function will not work."""

    if serialized is None or serialized is Undefined:
        return NullValueNode()

    if isinstance(serialized, Mapping):
        field_items = (
            (key, ast_from_serialized_value_untyped(value))
            for key, value in serialized.items()
        )
        field_nodes = (
            ObjectFieldNode(name=NameNode(value=field_name), value=field_value)
            for field_name, field_value in field_items
            if field_value
        )
        return ObjectValueNode(fields=FrozenList(field_nodes))

    if isinstance(serialized, Iterable) and not isinstance(serialized, str):
        maybe_nodes = (ast_from_serialized_value_untyped(item) for item in serialized)
        nodes = filter(None, maybe_nodes)
        return ListValueNode(values=FrozenList(nodes))

    if isinstance(serialized, bool):
        return BooleanValueNode(value=serialized)

    if isinstance(serialized, int):
        return IntValueNode(value=f"{serialized:d}")

    if isinstance(serialized, float) and isfinite(serialized):
        return FloatValueNode(value=f"{serialized:g}")

    if isinstance(serialized, str):
        return StringValueNode(value=serialized)

    raise TypeError(f"Cannot convert value to AST: {inspect(serialized)}.")


def ast_from_value(value: Any, type_: GraphQLInputType) -> Optional[ValueNode]:
    """
    This is a partial copy paste of the ast_from_value function in
    graphql-core utilities/ast_from_value.py

    Overwrite the if blocks that use recursion and add a new case to return a
    VariableNode when value is a DSLVariable

    Produce a GraphQL Value AST given a Python object.

    Raises a GraphQLError instead of returning None if we receive an Undefined
    of if we receive a Null value for a Non-Null type.
    """
    if isinstance(value, DSLVariable):
        return value.set_type(type_).ast_variable

    if is_non_null_type(type_):
        type_ = cast(GraphQLNonNull, type_)
        inner_type = type_.of_type
        ast_value = ast_from_value(value, inner_type)
        if isinstance(ast_value, NullValueNode):
            raise GraphQLError(
                "Received Null value for a Non-Null type " f"{inspect(inner_type)}."
            )
        return ast_value

    # only explicit None, not Undefined or NaN
    if value is None:
        return NullValueNode()

    # undefined
    if value is Undefined:
        raise GraphQLError(f"Received Undefined value for type {inspect(type_)}.")

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

    if is_leaf_type(type_):
        # Since value is an internally represented value, it must be serialized to an
        # externally represented value before converting into an AST.
        serialized = type_.serialize(value)  # type: ignore

        # if the serialized value is a string, then we should use the
        # type to determine if it is an enum, an ID or a normal string
        if isinstance(serialized, str):
            # Enum types use Enum literals.
            if is_enum_type(type_):
                return EnumValueNode(value=serialized)

            # ID types can use Int literals.
            if type_ is GraphQLID and _re_integer_string.match(serialized):
                return IntValueNode(value=serialized)

            return StringValueNode(value=serialized)

        # Some custom scalars will serialize to dicts or lists
        # Providing here a default conversion to AST using our best judgment
        # until graphql-js issue #1817 is solved
        # https://github.com/graphql/graphql-js/issues/1817
        return ast_from_serialized_value_untyped(serialized)

    # Not reachable. All possible input types have been considered.
    raise TypeError(f"Unexpected input type: {inspect(type_)}.")


def dsl_gql(
    *operations: "DSLExecutable", **operations_with_name: "DSLExecutable"
) -> DocumentNode:
    r"""Given arguments instances of :class:`DSLExecutable`
    containing GraphQL operations or fragments,
    generate a Document which can be executed later in a
    gql client or a gql session.

    Similar to the :func:`gql.gql` function but instead of parsing a python
    string to describe the request, we are using operations which have been generated
    dynamically using instances of :class:`DSLField`, generated
    by instances of :class:`DSLType` which themselves originated from
    a :class:`DSLSchema` class.

    :param \*operations: the GraphQL operations and fragments
    :type \*operations: DSLQuery, DSLMutation, DSLSubscription, DSLFragment
    :param \**operations_with_name: the GraphQL operations with an operation name
    :type \**operations_with_name: DSLQuery, DSLMutation, DSLSubscription

    :return: a Document which can be later executed or subscribed by a
        :class:`Client <gql.client.Client>`, by an
        :class:`async session <gql.client.AsyncClientSession>` or by a
        :class:`sync session <gql.client.SyncClientSession>`

    :raises TypeError: if an argument is not an instance of :class:`DSLExecutable`
    :raises AttributeError: if a type has not been provided in a :class:`DSLFragment`
    """

    # Concatenate operations without and with name
    all_operations: Tuple["DSLExecutable", ...] = (
        *operations,
        *(operation for operation in operations_with_name.values()),
    )

    # Set the operation name
    for name, operation in operations_with_name.items():
        operation.name = name

    # Check the type
    for operation in all_operations:
        if not isinstance(operation, DSLExecutable):
            raise TypeError(
                "Operations should be instances of DSLExecutable "
                "(DSLQuery, DSLMutation, DSLSubscription or DSLFragment).\n"
                f"Received: {type(operation)}."
            )

    return DocumentNode(
        definitions=[operation.executable_ast for operation in all_operations]
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

        assert isinstance(type_def, (GraphQLObjectType, GraphQLInterfaceType))

        return DSLType(type_def)


class DSLExecutable(ABC):
    """Interface for the root elements which can be executed
    in the :func:`dsl_gql <gql.dsl.dsl_gql>` function

    Inherited by
    :class:`DSLOperation <gql.dsl.DSLOperation>` and
    :class:`DSLFragment <gql.dsl.DSLFragment>`
    """

    variable_definitions: "DSLVariableDefinitions"
    name: Optional[str]

    @property
    @abstractmethod
    def executable_ast(self):
        """Generates the ast for :func:`dsl_gql <gql.dsl.dsl_gql>`."""
        raise NotImplementedError(
            "Any DSLExecutable subclass must have executable_ast property"
        )  # pragma: no cover

    def __init__(
        self, *fields: "DSLSelectable", **fields_with_alias: "DSLSelectableWithAlias",
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

        self.name = None
        self.variable_definitions = DSLVariableDefinitions()

        # Concatenate fields without and with alias
        all_fields: Tuple["DSLSelectable", ...] = DSLField.get_aliased_fields(
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
            if isinstance(self, DSLOperation):
                assert field.type_name.upper() == self.operation_type.name, (
                    f"Invalid root field for operation {self.operation_type.name}.\n"
                    f"Received: {field.type_name}"
                )

        self.selection_set = SelectionSetNode(
            selections=FrozenList(DSLSelectable.get_ast_fields(all_fields))
        )


class DSLOperation(DSLExecutable):
    """Interface for GraphQL operations.

    Inherited by
    :class:`DSLQuery <gql.dsl.DSLQuery>`,
    :class:`DSLMutation <gql.dsl.DSLMutation>` and
    :class:`DSLSubscription <gql.dsl.DSLSubscription>`
    """

    operation_type: OperationType

    @property
    def executable_ast(self) -> OperationDefinitionNode:
        """Generates the ast for :func:`dsl_gql <gql.dsl.dsl_gql>`."""

        return OperationDefinitionNode(
            operation=OperationType(self.operation_type),
            selection_set=self.selection_set,
            variable_definitions=FrozenList(
                self.variable_definitions.get_ast_definitions()
            ),
            **({"name": NameNode(value=self.name)} if self.name else {}),
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


class DSLSelectable(ABC):
    """DSLSelectable is an abstract class which indicates that
    the subclasses can be used as arguments of the
    :meth:`select <gql.dsl.DSLSelector.select>` method.

    Inherited by
    :class:`DSLField <gql.dsl.DSLField>`,
    :class:`DSLFragment <gql.dsl.DSLFragment>`
    :class:`DSLInlineFragment <gql.dsl.DSLInlineFragment>`
    """

    ast_field: Union[FieldNode, InlineFragmentNode, FragmentSpreadNode]

    @staticmethod
    def get_ast_fields(
        fields: Iterable["DSLSelectable"],
    ) -> List[Union[FieldNode, InlineFragmentNode, FragmentSpreadNode]]:
        """
        :meta private:

        Equivalent to: :code:`[field.ast_field for field in fields]`
        But with a type check for each field in the list.

        :raises TypeError: if any of the provided fields are not instances
                           of the :class:`DSLSelectable` class.
        """
        ast_fields = []
        for field in fields:
            if isinstance(field, DSLSelectable):
                ast_fields.append(field.ast_field)
            else:
                raise TypeError(f'Received incompatible field: "{field}".')

        return ast_fields

    @staticmethod
    def get_aliased_fields(
        fields: Iterable["DSLSelectable"],
        fields_with_alias: Dict[str, "DSLSelectableWithAlias"],
    ) -> Tuple["DSLSelectable", ...]:
        """
        :meta private:

        Concatenate all the fields (with or without alias) in a Tuple.

        Set the requested alias for the fields with alias.
        """

        return (
            *fields,
            *(field.alias(alias) for alias, field in fields_with_alias.items()),
        )

    def __str__(self) -> str:
        return print_ast(self.ast_field)


class DSLSelector(ABC):
    """DSLSelector is an abstract class which defines the
    :meth:`select <gql.dsl.DSLSelector.select>` method to select
    children fields in the query.

    Inherited by
    :class:`DSLField <gql.dsl.DSLField>`,
    :class:`DSLFragment <gql.dsl.DSLFragment>`,
    :class:`DSLInlineFragment <gql.dsl.DSLInlineFragment>`
    """

    selection_set: SelectionSetNode

    def __init__(self):
        self.selection_set = SelectionSetNode(selections=FrozenList([]))

    def select(
        self, *fields: "DSLSelectable", **fields_with_alias: "DSLSelectableWithAlias"
    ) -> "DSLSelector":
        r"""Select the new children fields
        that we want to receive in the request.

        If used multiple times, we will add the new children fields
        to the existing children fields.

        :param \*fields: new children fields
        :type \*fields: DSLSelectable (DSLField, DSLFragment or DSLInlineFragment)
        :param \**fields_with_alias: new children fields with alias as key
        :type \**fields_with_alias: DSLField
        :return: itself

        :raises TypeError: if any of the provided fields are not instances
                           of the :class:`DSLSelectable` class.
        """

        # Concatenate fields without and with alias
        added_fields: Tuple["DSLSelectable", ...] = DSLSelectable.get_aliased_fields(
            fields, fields_with_alias
        )

        # Get a list of AST Nodes for each added field
        added_selections: List[
            Union[FieldNode, InlineFragmentNode, FragmentSpreadNode]
        ] = DSLSelectable.get_ast_fields(added_fields)

        # Update the current selection list with new selections
        self.selection_set.selections = FrozenList(
            self.selection_set.selections + added_selections
        )

        log.debug(f"Added fields: {added_fields} in {self!r}")

        return self


class DSLSelectableWithAlias(DSLSelectable):
    """DSLSelectableWithAlias is an abstract class which indicates that
    the subclasses can be selected with an alias.
    """

    ast_field: FieldNode

    def alias(self, alias: str) -> "DSLSelectableWithAlias":
        """Set an alias

        .. note::
            You can also pass the alias directly at the
            :meth:`select <gql.dsl.DSLSelector.select>` method.
            :code:`ds.Query.human.select(my_name=ds.Character.name)` is equivalent to:
            :code:`ds.Query.human.select(ds.Character.name.alias("my_name"))`

        :param alias: the alias
        :type alias: str
        :return: itself
        """

        self.ast_field.alias = NameNode(value=alias)
        return self


class DSLField(DSLSelectableWithAlias, DSLSelector):
    """The DSLField represents a GraphQL field for the DSL code.

    Instances of this class are generated for you automatically as attributes
    of the :class:`DSLType`

    If this field contains children fields, then you need to select which ones
    you want in the request using the :meth:`select <gql.dsl.DSLField.select>`
    method.
    """

    _type: Union[GraphQLObjectType, GraphQLInterfaceType]
    ast_field: FieldNode
    field: GraphQLField

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
        DSLSelector.__init__(self)
        self._type = graphql_type
        self.field = graphql_field
        self.ast_field = FieldNode(name=NameNode(value=name), arguments=FrozenList())
        log.debug(f"Creating {self!r}")

    def __call__(self, **kwargs) -> "DSLField":
        return self.args(**kwargs)

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

    def select(
        self, *fields: "DSLSelectable", **fields_with_alias: "DSLSelectableWithAlias"
    ) -> "DSLField":
        """Calling :meth:`select <gql.dsl.DSLSelector.select>` method with
        corrected typing hints
        """

        super().select(*fields, **fields_with_alias)
        self.ast_field.selection_set = self.selection_set

        return self

    @property
    def type_name(self):
        """:meta private:"""
        return self._type.name

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} {self._type.name}"
            f"::{self.ast_field.name.value}>"
        )


class DSLInlineFragment(DSLSelectable, DSLSelector):
    """DSLInlineFragment represents an inline fragment for the DSL code."""

    _type: Union[GraphQLObjectType, GraphQLInterfaceType]
    ast_field: InlineFragmentNode

    def __init__(
        self, *fields: "DSLSelectable", **fields_with_alias: "DSLSelectableWithAlias",
    ):
        r"""Initialize the DSLInlineFragment.

        :param \*fields: new children fields
        :type \*fields: DSLSelectable (DSLField, DSLFragment or DSLInlineFragment)
        :param \**fields_with_alias: new children fields with alias as key
        :type \**fields_with_alias: DSLField
        """

        DSLSelector.__init__(self)
        self.ast_field = InlineFragmentNode()
        self.select(*fields, **fields_with_alias)
        log.debug(f"Creating {self!r}")

    def select(
        self, *fields: "DSLSelectable", **fields_with_alias: "DSLSelectableWithAlias"
    ) -> "DSLInlineFragment":
        """Calling :meth:`select <gql.dsl.DSLSelector.select>` method with
        corrected typing hints
        """
        super().select(*fields, **fields_with_alias)
        self.ast_field.selection_set = self.selection_set

        return self

    def on(self, type_condition: DSLType) -> "DSLInlineFragment":
        """Provides the GraphQL type of this inline fragment."""

        self._type = type_condition._type
        self.ast_field.type_condition = NamedTypeNode(
            name=NameNode(value=self._type.name)
        )
        return self

    def __repr__(self) -> str:
        type_info = ""

        try:
            type_info += f" on {self._type.name}"
        except AttributeError:
            pass

        return f"<{self.__class__.__name__}{type_info}>"


class DSLFragment(DSLSelectable, DSLSelector, DSLExecutable):
    """DSLFragment represents a named GraphQL fragment for the DSL code."""

    _type: Optional[Union[GraphQLObjectType, GraphQLInterfaceType]]
    ast_field: FragmentSpreadNode
    name: str

    def __init__(
        self,
        name: str,
        *fields: "DSLSelectable",
        **fields_with_alias: "DSLSelectableWithAlias",
    ):
        r"""Initialize the DSLFragment.

        :param name: the name of the fragment
        :type name: str
        :param \*fields: new children fields
        :type \*fields: DSLSelectable (DSLField, DSLFragment or DSLInlineFragment)
        :param \**fields_with_alias: new children fields with alias as key
        :type \**fields_with_alias: DSLField
        """

        DSLSelector.__init__(self)
        DSLExecutable.__init__(self, *fields, **fields_with_alias)

        self.name = name
        self._type = None

        log.debug(f"Creating {self!r}")

    @property  # type: ignore
    def ast_field(self) -> FragmentSpreadNode:  # type: ignore
        """ast_field property will generate a FragmentSpreadNode with the
        provided name.

        Note: We need to ignore the type because of
        `issue #4125 of mypy <https://github.com/python/mypy/issues/4125>`_.
        """

        spread_node = FragmentSpreadNode()
        spread_node.name = NameNode(value=self.name)

        return spread_node

    def select(
        self, *fields: "DSLSelectable", **fields_with_alias: "DSLSelectableWithAlias"
    ) -> "DSLFragment":
        """Calling :meth:`select <gql.dsl.DSLSelector.select>` method with
        corrected typing hints
        """
        super().select(*fields, **fields_with_alias)

        return self

    def on(self, type_condition: DSLType) -> "DSLFragment":
        """Provides the GraphQL type of this fragment.

        :param type_condition: the provided type
        :type type_condition: DSLType
        """

        self._type = type_condition._type

        return self

    @property
    def executable_ast(self) -> FragmentDefinitionNode:
        """Generates the ast for :func:`dsl_gql <gql.dsl.dsl_gql>`.

        :raises AttributeError: if a type has not been provided
        """
        assert self.name is not None

        if self._type is None:
            raise AttributeError(
                "Missing type condition. Please use .on(type_condition) method"
            )

        return FragmentDefinitionNode(
            type_condition=NamedTypeNode(name=NameNode(value=self._type.name)),
            selection_set=self.selection_set,
            variable_definitions=FrozenList(
                self.variable_definitions.get_ast_definitions()
            ),
            name=NameNode(value=self.name),
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name!s}>"
