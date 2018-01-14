from pygql.transport.requests import RequestsHTTPTransport
import requests
from graphql.language.printer import print_ast
from graphql.execution import ExecutionResult
import concurrent.futures
import time
import threading

import sys

if sys.version_info >= (3, 0):
    import queue
else:
    import Queue as queue


class FutureExecResult(ExecutionResult):
    def __init__(self, future):
        self.future = future
        self._data = None
        self._errors = None
        self._invalid = False
        self.filled = False

    def _fill_data(self):
        if not self.filled:
            result = self.future.result()
            self._errors = result.get('errors')
            self._data = result.get('data')
            self.filled = True

    @property
    def data(self):
        self._fill_data()
        return self._data

    @property
    def errors(self):
        self._fill_data()
        return self._errors

    @property
    def invalid(self):
        self._fill_data()
        return self._invalid


class BatchTransport(RequestsHTTPTransport):
    def __init__(self, url, cookies, **kwargs):
        """
        :param url: The GraphQL URL
        :param auth: Auth tuple or callable to enable Basic/Digest/Custom HTTP Auth
        :param use_json: Send request body as JSON instead of form-urlencoded
        :param timeout: Specifies a default timeout for requests (Default: None)
        """
        super(BatchTransport, self).__init__(url, **kwargs)
        self.session = requests.Session()
        self.cookies = cookies
        self.session.cookies = requests.utils.cookiejar_from_dict(self.cookies)
        self.session.headers.update(self.headers)
        self.session.auth = self.auth
        self.query_batcher_active = True

        self.timeout = self.default_timeout
        self.data_key = 'json' if self.use_json else 'data'

        self.query_batcher_queue = queue.Queue()
        self.query_batcher = threading.Thread(target=self._batch_query, daemon=True)
        self.query_batcher.start()

    def _batch_query(self):
        while self.query_batcher_active:
            query_payloads = []
            futures = []
            payload, future = self.query_batcher_queue.get()

            if not self.query_batcher_active:
                break
            query_payloads.append(payload)
            futures.append(future)
            # wait 10 ms
            time.sleep(0.01)
            while not self.query_batcher_queue.empty():
                if not self.query_batcher_active:
                    break
                payload, future = self.query_batcher_queue.get()
                query_payloads.append(payload)
                futures.append(future)

            new_futures = []
            new_query_payloads = []
            for payload, future in zip(query_payloads, futures):

                if future.set_running_or_notify_cancel():
                    new_futures.append(future)
                    new_query_payloads.append(payload)

            try:
                post_args = {
                    'timeout': self.timeout,
                    self.data_key: new_query_payloads
                }

                request = self.session.post(self.url, **post_args)
                request.raise_for_status()
                results = request.json()
                for result, future in zip(results, new_futures):
                    try:

                        assert 'errors' in result or 'data' in result, \
                                'Received non-compatible response "{}"'.format(result)
                        future.set_result(result)
                    except Exception as exc:
                        future.set_exception(exc)
            except Exception as exc:
                for future in new_futures:
                    future.set_exception(exc)

    def set_timeout(self, timeout):
        self.timeout = timeout

    def execute(self, document, variable_values=None, timeout=None):
        query_str = print_ast(document)
        payload = {
            'query': query_str,
            'variables': variable_values or {}
        }
        future = concurrent.futures.Future()
        self.query_batcher_queue.put((payload, future))

        return FutureExecResult(future)
