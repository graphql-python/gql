from __future__ import absolute_import

import requests
from graphql.execution import ExecutionResult
from graphql.language.printer import print_ast

from .http import HTTPTransport


class RequestsHTTPTransport(HTTPTransport):
    def __init__(self, auth=None, timeout=None, *args, **kwargs):
        super(RequestsHTTPTransport, self).__init__(*args, **kwargs)
        self.auth = auth
        self.default_timeout = timeout

    def execute(self, document, variable_values=None, timeout=None):
        query_str = print_ast(document)
        request = requests.post(
            self.url,
            data={
                'query': query_str,
                'variables': variable_values
            },
            headers=self.headers,
            auth=self.auth,
            timeout=timeout or self.default_timeout
        )
        request.raise_for_status()

        result = request.json()
        assert 'errors' in result or 'data' in result, 'Received non-compatible response "{}"'.format(result)
        return ExecutionResult(
            errors=result.get('errors'),
            data=result.get('data')
        )
