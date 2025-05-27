from typing import Any, Dict, Optional, Union

from graphql import DocumentNode, GraphQLSchema, print_ast

from .gql import gql
from .utilities import serialize_variable_values


class GraphQLRequest:
    """GraphQL Request to be executed."""

    def __init__(
        self,
        document: Union[DocumentNode, str],
        *,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ):
        """
        Initialize a GraphQL request.

        Args:
            document: GraphQL query as AST Node object or as a string.
                     If string, it will be converted to DocumentNode using gql().
            variable_values: Dictionary of input parameters (Default: None).
            operation_name: Name of the operation that shall be executed.
                          Only required in multi-operation documents (Default: None).
        """
        if isinstance(document, str):
            self.document = gql(document)
        else:
            self.document = document

        self.variable_values = variable_values
        self.operation_name = operation_name

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

    def __str__(self):
        return str(self.payload)
