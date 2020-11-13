import logging
from collections.abc import Iterable
from typing import List, Optional, Union

from graphql import (
    ArgumentNode,
    DocumentNode,
    FieldNode,
    GraphQLArgument,
    GraphQLField,
    GraphQLInterfaceType,
    GraphQLNamedType,
    GraphQLObjectType,
    GraphQLSchema,
    NameNode,
    OperationDefinitionNode,
    OperationType,
    SelectionSetNode,
    ast_from_value,
    print_ast,
)
from graphql.pyutils import FrozenList

from .utils import to_camel_case

log = logging.getLogger(__name__)


def dsl_gql(*fields: "DSLField") -> DocumentNode:
    """Given arguments of type :class:`DSLField` containing GraphQL requests,
    generate a Document which can be executed later in a
    gql client or a gql session.

    Similar to the :func:`gql.gql` function but instead of parsing a python
    string to describe the request, we are using requests which have been generated
    dynamically using instances of :class:`DSLField`, generated
    by instances of :class:`DSLType` which themselves originated from
    a :class:`DSLSchema` class.

    The fields arguments should be fields of root GraphQL types
    (Query, Mutation or Subscription).

    They should all have the same root type
    (you can't mix queries with mutations for example).

    :param fields: root instances of the dynamically generated requests
    :type fields: DSLField
    :return: a Document which can be later executed or subscribed by a
        :class:`Client <gql.client.Client>`, by an
        :class:`async session <gql.client.AsyncClientSession>` or by a
        :class:`sync session <gql.client.SyncClientSession>`

    :raises TypeError: if an argument is not an instance of :class:`DSLField`
    :raises AssertionError: if an argument is not a field of a root type
    """

    # Check that we receive only arguments of type DSLField
    # And that they are a root type
    for field in fields:
        if not isinstance(field, DSLField):
            raise TypeError(
                f"fields must be instances of DSLField. Received type: {type(field)}"
            )
        assert field.type_name in ["Query", "Mutation", "Subscription"], (
            "fields should be root types (Query, Mutation or Subscription)\n"
            f"Received: {field.type_name}"
        )

    # Get the operation from the first field
    # All the fields must have the same operation
    operation = fields[0].type_name.lower()

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
    def get_ast_fields(fields: Iterable) -> List[FieldNode]:
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

        added_fields: List["DSLField"] = list(fields) + [
            field.alias(alias) for alias, field in fields_with_alias.items()
        ]

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
