from typing import Any, Dict, Callable, Optional, List

from graphql.type.schema import GraphQLSchema
from graphql.type.definition import GraphQLObjectType, GraphQLField, GraphQLScalarType


class ResponseParser(object):
    """The challenge is to substitute custom scalars in a GQL response with their
    decoded counterparts.

    To solve this problem, we first need to iterate over all the fields in the
    response (which is done in the `_traverse()` function).

    Each time we find a field which has type scalar and is a custom scalar, we
    need to replace the value of that field with the decoded value. All of this
    logic happens in `_substitute()`.

    Public Interface:
    parse(): call parse with a GQL response to replace all instances of custom
        scalar strings with their deserialized representation."""

    def __init__(self, schema: GraphQLSchema, custom_scalars: Dict[str, Any] = {}) -> None:
        """ schema: a graphQL schema in the GraphQLSchema format
            custom_scalars: a Dict[str, Any],
                where str is the name of the custom scalar type, and
                      Any is a class which has a `parse_value()` function"""
        self.schema = schema
        self.custom_scalars = custom_scalars

    def _follow_type_chain(self, node: Any) -> Any:
        """In the schema GraphQL types are often listed with the format
        `obj.type.of_type...` where there are 0 or more 'of_type' fields before
        you get to the type you are interested in.

        This is a convenience method to help us get to these nested types."""
        if isinstance(node, GraphQLObjectType):
            return node

        field_type = node.type
        while hasattr(field_type, 'of_type'):
            field_type = field_type.of_type

        return field_type

    def _get_scalar_type_name(self, field: GraphQLField) -> Optional[str]:
        """Returns the name of the type if the type is a scalar type.
        Returns None otherwise"""
        node = self._follow_type_chain(field)
        if isinstance(node, GraphQLScalarType):
            return node.name
        return None

    def _lookup_scalar_type(self, keys: List[str]) -> Optional[str]:
        """
        `keys` is a breadcrumb trail telling us where to look in the GraphQL schema.
        By default the root level is `schema.query`, if that fails, then we check
        `schema.mutation`.

        If keys (e.g. ['wallet', 'balance']) points to a scalar type, then
        this function returns the name of that type. (e.g. 'Money')

        If it is not a scalar type (e..g a GraphQLObject or list), then this
        function returns None"""

        def iterate(node: Any, lookup: List[str]):
            lookup = lookup.copy()
            if not lookup:
                return self._get_scalar_type_name(node)

            final_node = self._follow_type_chain(node)
            return iterate(final_node.fields[lookup.pop(0)], lookup)

        try:
            return iterate(self.schema.get_query_type(), keys)
        except (KeyError, AttributeError):
            try:
                return iterate(self.schema.get_mutation_type(), keys)
            except (KeyError, AttributeError):
                return None

    def _substitute(self, keys: List[str], value: Any) -> Any:
        """Looks in the GraphQL schema to find the type identified by 'keys'

        If that type is not a custom scalar, we return the original value.
        If it is a custom scalar, we return the deserialized value, as
        processed by `<CustomScalarType>.parse_value()`"""
        scalar_type = self._lookup_scalar_type(keys)
        if scalar_type and scalar_type in self.custom_scalars:
            return self.custom_scalars[scalar_type].parse_value(value)
        return value

    def _traverse(self, response: Dict[str, Any], substitute: Callable) -> Dict[str, Any]:
        """Recursively traverses the GQL response and calls the `substitute`
        function on all leaf nodes. The function is called with 2 arguments:
            keys: List[str] is a breadcrumb trail telling us where we are in the
                response, and therefore, where to look in the GQL Schema.
            value: Any is the value at that node in the tree

        Builds a new tree with the substituted values so `response` is not
        modified."""
        def iterate(node: Any, keys: List[str] = []):
            if isinstance(node, dict):
                result = {}
                for _key, value in node.items():
                    result[_key] = iterate(value, keys + [_key])
                return result
            elif isinstance(node, list):
                return [(iterate(item, keys)) for item in node]
            else:
                return substitute(keys, node)
        return iterate(response)

    def parse(self, response: Dict[str, Any]) -> Dict[str, Any]:
        return self._traverse(response, self._substitute)
