from __future__ import absolute_import

import requests
from graphql.execution import ExecutionResult
from graphql.language.printer import print_ast


class RequestsHTTPTransport(object):
    def __init__(self, url, headers=None, cookies=None, auth=None, use_json=False, timeout=None, verify=True, **kwargs):
        """
        :param url: The GraphQL URL
        :param auth: (optional) Auth tuple or callable to enable Basic/Digest/Custom HTTP Auth
        :param use_json: (optional) Send request body as JSON instead of form-urlencoded
        :param timeout: (optional) Specifies a default timeout for requests (Default: None)
        :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
        :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
        :param verify: (optional) Either a boolean, in which case it controls whether we verify
            the server's TLS certificate, or a string, in which case it must be a path
            to a CA bundle to use. Defaults to ``True``.
        :param **kwargs: Optional arguments that ``request`` takes. These can be seen at the request source code at
            https://github.com/psf/requests/blob/master/requests/api.py or the official documentation at
            https://requests.readthedocs.io/en/master/.
        """
        self.url = url
        self.headers = headers
        self.cookies = cookies
        self.auth = auth
        self.use_json = use_json
        self.default_timeout = timeout
        self.verify = verify
        self.kwargs = kwargs

    def execute(self, document, variable_values=None, timeout=None):
        query_str = print_ast(document)
        payload = {
            'query': query_str,
            'variables': variable_values or {}
        }

        data_key = 'json' if self.use_json else 'data'
        post_args = {
            'headers': self.headers,
            'auth': self.auth,
            'cookies': self.cookies,
            'timeout': timeout or self.default_timeout,
            'verify': self.verify,
            data_key: payload
        }

        # Pass kwargs to requests post method
        post_args.update(self.kwargs)

        response = requests.post(self.url, **post_args)
        try:
            result = response.json()
            if not isinstance(result, dict):
                raise ValueError
        except ValueError:
            result = {}

        if 'errors' not in result and 'data' not in result:
            response.raise_for_status()
            raise requests.HTTPError("Server did not return a GraphQL result", response=response)
        return ExecutionResult(errors=result.get('errors'), data=result.get('data'))
