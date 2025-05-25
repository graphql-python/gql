from dataclasses import dataclass
from typing import Any, Dict, Optional

from graphql import DocumentNode, GraphQLSchema, print_ast

from .utilities import serialize_variable_values


@dataclass(frozen=True)
class GraphQLRequest:
    """GraphQL Request to be executed."""

    document: DocumentNode
    """GraphQL query as AST Node object."""

    variable_values: Optional[Dict[str, Any]] = None
    """Dictionary of input parameters (Default: None)."""

    operation_name: Optional[str] = None
    """
    Name of the operation that shall be executed.
    Only required in multi-operation documents (Default: None).
    """

    def serialize_variable_values(self, schema: GraphQLSchema) -> "GraphQLRequest":
        assert self.variable_values

        return GraphQLRequest(
            document=self.document,
            variable_values=serialize_variable_values(
                schema=schema,
                document=self.document,
                variable_values=self.variable_values,
                operation_name=self.operation_name,
            ),
            operation_name=self.operation_name,
        )

    @property
    def payload(self) -> Dict[str, Any]:
        query_str = print_ast(self.document)
        payload: Dict[str, Any] = {"query": query_str}

        if self.operation_name:
            payload["operationName"] = self.operation_name

        if self.variable_values:
            payload["variables"] = self.variable_values

        return payload
