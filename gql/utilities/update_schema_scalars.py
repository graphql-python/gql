from typing import Iterable, List

from graphql import GraphQLScalarType, GraphQLSchema


def update_schema_scalar(schema: GraphQLSchema, name: str, scalar: GraphQLScalarType):
    """Update the scalar in a schema with the scalar provided.

    This can be used to update the default Custom Scalar implementation
    when the schema has been provided from a text file or from introspection.
    """

    if not isinstance(scalar, GraphQLScalarType):
        raise TypeError("Scalars should be instances of GraphQLScalarType.")

    schema_scalar = schema.get_type(name)

    if schema_scalar is None:
        raise KeyError(f"Scalar '{name}' not found in schema.")

    if not isinstance(schema_scalar, GraphQLScalarType):
        raise TypeError(
            f'The type "{name}" is not a GraphQLScalarType,'
            f"it is a {type(schema_scalar)}"
        )

    # Update the conversion methods
    # Using setattr because mypy has a false positive
    # https://github.com/python/mypy/issues/2427
    setattr(schema_scalar, "serialize", scalar.serialize)
    setattr(schema_scalar, "parse_value", scalar.parse_value)
    setattr(schema_scalar, "parse_literal", scalar.parse_literal)


def update_schema_scalars(schema: GraphQLSchema, scalars: List[GraphQLScalarType]):
    """Update the scalars in a schema with the scalars provided.

    This can be used to update the default Custom Scalar implementation
    when the schema has been provided from a text file or from introspection.
    """

    if not isinstance(scalars, Iterable):
        raise TypeError("Scalars argument should be a list of scalars.")

    for scalar in scalars:
        if not isinstance(scalar, GraphQLScalarType):
            raise TypeError("Scalars should be instances of GraphQLScalarType.")

        update_schema_scalar(schema, scalar.name, scalar)
