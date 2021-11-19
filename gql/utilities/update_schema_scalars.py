from typing import Iterable, List

from graphql import GraphQLError, GraphQLScalarType, GraphQLSchema


def update_schema_scalars(schema: GraphQLSchema, scalars: List[GraphQLScalarType]):
    """Update the scalars in a schema with the scalars provided.

    This can be used to update the default Custom Scalar implementation
    when the schema has been provided from a text file or from introspection.
    """

    if not isinstance(scalars, Iterable):
        raise GraphQLError("Scalars argument should be a list of scalars.")

    for scalar in scalars:
        if not isinstance(scalar, GraphQLScalarType):
            raise GraphQLError("Scalars should be instances of GraphQLScalarType.")

        try:
            schema_scalar = schema.type_map[scalar.name]
        except KeyError:
            raise GraphQLError(f"Scalar '{scalar.name}' not found in schema.")

        assert isinstance(schema_scalar, GraphQLScalarType)

        # Update the conversion methods
        # Using setattr because mypy has a false positive
        # https://github.com/python/mypy/issues/2427
        setattr(schema_scalar, "serialize", scalar.serialize)
        setattr(schema_scalar, "parse_value", scalar.parse_value)
        setattr(schema_scalar, "parse_literal", scalar.parse_literal)
