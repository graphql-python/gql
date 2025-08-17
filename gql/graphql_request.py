import warnings
from typing import Any, Dict, Optional, Union

from graphql import DocumentNode, GraphQLSchema, Source, parse, print_ast


class GraphQLRequest:
    """GraphQL Request to be executed."""

    def __init__(
        self,
        request: Union[DocumentNode, "GraphQLRequest", str],
        *,
        variable_values: Optional[Dict[str, Any]] = None,
        operation_name: Optional[str] = None,
    ):
        """Initialize a GraphQL request.

        :param request: GraphQL request as DocumentNode object or as a string.
             If string, it will be converted to DocumentNode.
        :param variable_values: Dictionary of input parameters (Default: None).
        :param operation_name: Name of the operation that shall be executed.
            Only required in multi-operation documents (Default: None).
        :return: a :class:`GraphQLRequest <gql.GraphQLRequest>`
                 which can be later executed or subscribed by a
                 :class:`Client <gql.client.Client>`, by an
                 :class:`async session <gql.client.AsyncClientSession>` or by a
                 :class:`sync session <gql.client.SyncClientSession>`
        :raises graphql.error.GraphQLError: if a syntax error is encountered.
        """
        if isinstance(request, str):
            source = Source(request, "GraphQL request")
            self.document = parse(source)
        elif isinstance(request, DocumentNode):
            self.document = request
        elif not isinstance(request, GraphQLRequest):
            raise TypeError(f"Unexpected type for GraphQLRequest: {type(request)}")

        if isinstance(request, GraphQLRequest):
            self.document = request.document
            if variable_values is None:
                variable_values = request.variable_values
            if operation_name is None:
                operation_name = request.operation_name

        self.variable_values: Optional[Dict[str, Any]] = variable_values
        self.operation_name: Optional[str] = operation_name

    def serialize_variable_values(self, schema: GraphQLSchema) -> "GraphQLRequest":

        from .utilities.serialize_variable_values import serialize_variable_values

        assert self.variable_values

        return GraphQLRequest(
            self.document,
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


def support_deprecated_request(
    request: Union[GraphQLRequest, DocumentNode],
    kwargs: Dict,
) -> GraphQLRequest:
    """This methods is there temporarily to convert the old style of calling
    execute and subscribe methods with a DocumentNode,
    variable_values and operation_name arguments.
    """

    if isinstance(request, DocumentNode):
        warnings.warn(
            (
                "Using a DocumentNode is deprecated. Please use a "
                "GraphQLRequest instead."
            ),
            DeprecationWarning,
            stacklevel=2,
        )
        request = GraphQLRequest(request)

    if not isinstance(request, GraphQLRequest):
        raise TypeError("request should be a GraphQLRequest object")

    variable_values = kwargs.pop("variable_values", None)
    operation_name = kwargs.pop("operation_name", None)

    if variable_values or operation_name:
        warnings.warn(
            (
                "Using variable_values and operation_name arguments of "
                "execute and subscribe methods is deprecated. Instead, "
                "please use the variable_values and operation_name properties "
                "of GraphQLRequest"
            ),
            DeprecationWarning,
            stacklevel=2,
        )

        request.variable_values = variable_values
        request.operation_name = operation_name

    return request
