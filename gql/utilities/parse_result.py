from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union, cast

from graphql import (
    IDLE,
    REMOVE,
    DocumentNode,
    FieldNode,
    FragmentDefinitionNode,
    FragmentSpreadNode,
    GraphQLEnumType,
    GraphQLError,
    GraphQLScalarType,
    GraphQLSchema,
    InlineFragmentNode,
    NameNode,
    OperationDefinitionNode,
    SelectionSetNode,
    TypeInfo,
    TypeInfoVisitor,
    Visitor,
    get_nullable_type,
    is_nullable_type,
    visit,
)
from graphql.language.visitor import VisitorActionEnum

# Equivalent to QUERY_DOCUMENT_KEYS but only for fields interesting to
# visit to parse the results
RESULT_DOCUMENT_KEYS: Dict[str, Tuple[str, ...]] = {
    "name": (),
    "document": ("definitions",),
    "operation_definition": ("name", "selection_set",),
    "selection_set": ("selections",),
    "field": ("alias", "name", "selection_set"),
    "fragment_spread": ("name",),
    "inline_fragment": ("type_condition", "selection_set"),
    "fragment_definition": ("name", "type_condition", "selection_set",),
}


class ParseResultVisitor(Visitor):
    def __init__(
        self,
        schema: GraphQLSchema,
        document: DocumentNode,
        type_info: TypeInfo,
        result: Dict[str, Any],
        visit_fragment: bool = False,
    ):

        self.schema: GraphQLSchema = schema
        self.document: DocumentNode = document
        self.type_info: TypeInfo = type_info
        self.result: Dict[str, Any] = result
        self.visit_fragment: bool = visit_fragment

        self.result_stack: List[Any] = []

    @property
    def current_result(self):
        try:
            return self.result_stack[-1]
        except IndexError:
            return self.result

    def leave_name(self, node: NameNode, *_args: Any,) -> str:
        return node.value

    @staticmethod
    def leave_document(node: DocumentNode, *_args: Any) -> Dict[str, Any]:
        results = cast(List[Dict[str, Any]], node.definitions)
        return {k: v for result in results for k, v in result.items()}

    @staticmethod
    def leave_operation_definition(
        node: OperationDefinitionNode, *_args: Any
    ) -> Dict[str, Any]:
        selections = cast(List[Dict[str, Any]], node.selection_set)
        return {k: v for s in selections for k, v in s.items()}

    @staticmethod
    def leave_selection_set(node: SelectionSetNode, *_args: Any) -> Dict[str, Any]:
        partial_results = cast(Dict[str, Any], node.selections)
        return partial_results

    def enter_field(
        self, node: FieldNode, *_args: Any,
    ) -> Union[None, VisitorActionEnum, Dict[str, Any]]:

        name = node.alias.value if node.alias else node.name.value

        if isinstance(self.current_result, Mapping):
            if name in self.current_result:

                result_value = self.current_result[name]

                # If the result for this field is a list, then we need
                # to recursively visit the same node multiple times for each
                # item in the list.
                if (
                    not isinstance(result_value, Mapping)
                    and isinstance(result_value, Iterable)
                    and not isinstance(result_value, str)
                ):
                    visits: List[Dict[str, Any]] = []

                    for item in result_value:

                        new_result = {name: item}

                        inner_visit = cast(
                            Dict[str, Any],
                            visit(
                                node,
                                ParseResultVisitor(
                                    self.schema,
                                    self.document,
                                    self.type_info,
                                    new_result,
                                ),
                                visitor_keys=RESULT_DOCUMENT_KEYS,
                            ),
                        )

                        visits.append(inner_visit[name])

                    return {name: visits}

                # If the result for this field is not a list, then add it
                # to the result stack so that it becomes the current_value
                # for the next inner fields
                self.result_stack.append(result_value)

                return IDLE

            else:
                # Key not found in result.
                # Should never happen in theory with a correct GraphQL backend
                # Silently ignoring this field
                return REMOVE

        elif self.current_result is None:
            # Result was null for this field -> remove
            return REMOVE

        raise GraphQLError(
            f"Invalid result for container of field {name}: {self.current_result!r}"
        )

    def leave_field(self, node: FieldNode, *_args: Any,) -> Dict[str, Any]:

        name = cast(str, node.alias if node.alias else node.name)

        if self.current_result is None:
            return {name: None}
        elif node.selection_set is None:

            field_type = self.type_info.get_type()
            if is_nullable_type(field_type):
                field_type = get_nullable_type(field_type)  # type: ignore

            if isinstance(field_type, (GraphQLScalarType, GraphQLEnumType)):

                parsed_value = field_type.parse_value(self.current_result)
            else:
                parsed_value = self.current_result

            return_value = {name: parsed_value}
        else:

            partial_results = cast(List[Dict[str, Any]], node.selection_set)

            return_value = {
                name: {k: v for pr in partial_results for k, v in pr.items()}
            }

        # Go up a level in the result stack
        self.result_stack.pop()

        return return_value

    # Fragments

    def enter_fragment_definition(
        self, node: FragmentDefinitionNode, *_args: Any
    ) -> Union[None, VisitorActionEnum]:

        if self.visit_fragment:
            return IDLE
        else:
            return REMOVE

    @staticmethod
    def leave_fragment_definition(
        node: FragmentDefinitionNode, *_args: Any
    ) -> Dict[str, Any]:

        selections = cast(List[Dict[str, Any]], node.selection_set)
        return {k: v for s in selections for k, v in s.items()}

    def leave_fragment_spread(
        self, node: FragmentSpreadNode, *_args: Any
    ) -> Dict[str, Any]:

        fragment_name = node.name

        for definition in self.document.definitions:
            if isinstance(definition, FragmentDefinitionNode):
                if definition.name.value == fragment_name:
                    fragment_result = visit(
                        definition,
                        ParseResultVisitor(
                            self.schema,
                            self.document,
                            self.type_info,
                            self.current_result,
                            visit_fragment=True,
                        ),
                        visitor_keys=RESULT_DOCUMENT_KEYS,
                    )
                    return fragment_result

        raise GraphQLError(f'Fragment "{fragment_name}" not found in schema!')

    @staticmethod
    def leave_inline_fragment(node: InlineFragmentNode, *_args: Any) -> Dict[str, Any]:

        selections = cast(List[Dict[str, Any]], node.selection_set)
        return {k: v for s in selections for k, v in s.items()}


def parse_result(
    schema: GraphQLSchema, document: DocumentNode, result: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Unserialize a result received from a GraphQL backend.

    Given a schema, a query and a serialized result,
    provide a new result with parsed values.

    If the result contains only built-in GraphQL scalars (String, Int, Float, ...)
    then the parsed result should be unchanged.

    If the result contains custom scalars or enums, then those values
    will be parsed with the parse_value method of the custom scalar or enum
    definition in the schema."""

    if result is None:
        return None

    type_info = TypeInfo(schema)

    visited = visit(
        document,
        TypeInfoVisitor(
            type_info, ParseResultVisitor(schema, document, type_info, result),
        ),
    )

    return visited
