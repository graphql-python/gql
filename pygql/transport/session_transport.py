from pygql.transport.requests import RequestsHTTPTransport
import requests
from graphql.language.printer import print_ast
from graphql.execution import ExecutionResult


class SessionTransport(RequestsHTTPTransport):
    def __init__(self, url, cookies, **kwargs):
        """
        :param url: The GraphQL URL
        :param auth: Auth tuple or callable to enable Basic/Digest/Custom HTTP Auth
        :param use_json: Send request body as JSON instead of form-urlencoded
        :param timeout: Specifies a default timeout for requests (Default: None)
        """
        super(SessionTransport, self).__init__(url, **kwargs)
        self.session = requests.Session()
        self.cookies = cookies
        self.session.cookies = requests.utils.cookiejar_from_dict(self.cookies)
        self.session.headers.update(self.headers)
        self.session.auth = self.auth

    def execute(self, document, variable_values=None, timeout=None):
        query_str = print_ast(document)
        payload = {
            'query': query_str,
            'variables': variable_values or {}
        }

        data_key = 'json' if self.use_json else 'data'
        post_args = {
            'timeout': timeout or self.default_timeout,
            data_key: payload
        }
        request = self.session.post(self.url, **post_args)
        request.raise_for_status()

        result = request.json()
        assert 'errors' in result or 'data' in result, 'Received non-compatible response "{}"'.format(result)
        return ExecutionResult(
            errors=result.get('errors'),
            data=result.get('data')
        )
