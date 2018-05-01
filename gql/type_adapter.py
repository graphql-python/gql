from graphql.type.definition import GraphQLObjectType, GraphQLScalarType


class TypeAdapter(object):
    """Substitute custom scalars in a GQL response with their decoded counterparts.

    GQL custom scalar types are defined on the GQL schema and are used to represent
    fields which have special behaviour. To define custom scalar type, you need
    the type name, and a class which has a class method called `parse_value()` -
    this is the function which will be used to deserialize the custom scalar field.

    We first need iterate over all the fields in the response (which is done in
    the `_traverse()` function).

    Each time we find a field which is a custom scalar (it's type name appears
    as a key in self.custom_types), we replace the value of that field with the
    decoded value. All of this logic happens in `_substitute()`.

    Public Interface:
    apply(): pass in a GQL response to replace all instances of custom
        scalar strings with their deserialized representation."""

    def __init__(self, schema, custom_types = {}):
        """ schema: a graphQL schema in the GraphQLSchema format
            custom_types: a Dict[str, Any],
                where str is the name of the custom scalar type, and
                      Any is a class which has a `parse_value(str)` function"""
        self.schema = schema
        self.custom_types = custom_types

    def _follow_type_chain(self, node):
        """ Get the type of the schema node in question.

        In the GraphQL schema, GraphQLFields have a "type" property. However, often
        that dict has an "of_type" property itself. In order to get to the actual
        type, we need to indefinitely follow the chain of "of_type" fields to get
        to the last one, which is the one we care about."""
        if isinstance(node, GraphQLObjectType):
            return node

        field_type = node.type
        while hasattr(field_type, 'of_type'):
            field_type = field_type.of_type

        return field_type

    def _get_scalar_type_name(self, field):
        """Returns the name of the type if the type is a scalar type.
        Returns None otherwise"""
        node = self._follow_type_chain(field)
        if isinstance(node, GraphQLScalarType):
            return node.name
        return None

    def _lookup_scalar_type(self, keys):
        """Search through the GQL schema and return the type identified by 'keys'.

        If keys (e.g. ['film', 'release_date']) points to a scalar type, then
        this function returns the name of that type. (e.g. 'DateTime')

        If it is not a scalar type (e..g a GraphQLObject), then this
        function returns None.

        `keys` is a breadcrumb trail telling us where to look in the GraphQL schema.
        By default the root level is `schema.query`, if that fails, then we check
        `schema.mutation`."""

        def traverse_schema(node, lookup):
            if not lookup:
                return self._get_scalar_type_name(node)

            final_node = self._follow_type_chain(node)
            return traverse_schema(final_node.fields[lookup[0]], lookup[1:])

        if keys[0] in self.schema.get_query_type().fields:
            schema_root = self.schema.get_query_type()
        elif keys[0] in self.schema.get_mutation_type().fields:
            schema_root = self.schema.get_mutation_type()
        else:
            return None

        try:
            return traverse_schema(schema_root, keys)
        except (KeyError, AttributeError):
            return None

    def _get_decoded_scalar_type(self, keys, value):
        """Get the decoded value of the type identified by `keys`.

        If the type is not a custom scalar, then return the original value.

        If it is a custom scalar, return the deserialized value, as
        output by `<CustomScalarType>.parse_value()`"""
        scalar_type = self._lookup_scalar_type(keys)
        if scalar_type and scalar_type in self.custom_types:
            return self.custom_types[scalar_type].parse_value(value)
        return value

    def convert_scalars(self, response):
        """Recursively traverse the GQL response

        Recursively traverses the GQL response and calls _get_decoded_scalar_type()
        for all leaf nodes. The function is called with 2 arguments:
            keys: List[str] is a breadcrumb trail telling us where we are in the
                response, and therefore, where to look in the GQL Schema.
            value: Any is the value at that node in the response

        Builds a new tree with the substituted values so old `response` is not
        modified."""
        def iterate(node, keys = []):
            if isinstance(node, dict):
                return {_key: iterate(value, keys + [_key]) for _key, value in node.items()}
            elif isinstance(node, list):
                return [(iterate(item, keys)) for item in node]
            else:
                return self._get_decoded_scalar_type(keys, node)
        return iterate(response)
