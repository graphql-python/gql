import pytest

from gql.transport.awsappsyncwebsocket import AppSyncWebsocketsTransport, AppSyncIAMAuthorization, AppSyncOIDCAuthorization, AppSyncApiKeyAuthorization

# TODO
# from gql.transport.exceptions import (
#     TransportAlreadyConnected,
#     TransportClosed,
#     TransportProtocolError,
#     TransportQueryError,
#     TransportServerError,
# )

# TODO:
# from .conftest import TemporaryFile

# TODO:
# query1_str = """
#     query getContinents {
#       continents {
#         code
#         name
#       }
#     }
# """

# TODO:
# query1_server_answer_data = (
#     '{"continents":['
#     '{"code":"AF","name":"Africa"},{"code":"AN","name":"Antarctica"},'
#     '{"code":"AS","name":"Asia"},{"code":"EU","name":"Europe"},'
#     '{"code":"NA","name":"North America"},{"code":"OC","name":"Oceania"},'
#     '{"code":"SA","name":"South America"}]}'
# )


# TODO:
# query1_server_answer = f'{{"data":{query1_server_answer_data}}}'

# Marking all tests in this file with the appsyncwebsocket marker
pytestmark = pytest.mark.appsyncwebsocket
mock_transport_url = "https://appsyncapp.awsgateway.com.example.org"

@pytest.mark.appsyncwebsocket
def test_appsyncwebsocket_init_with_minimal_args():
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url)
    assert isinstance(sample_transport.authorization, AppSyncIAMAuthorization)
    assert sample_transport.connect_timeout == 10
    assert sample_transport.close_timeout == 10
    assert sample_transport.ack_timeout == 10
    assert sample_transport.ssl == False
    assert sample_transport.connect_args == {}

def test_appsyncwebsocket_init_with_oidc_auth():
    authorization = AppSyncOIDCAuthorization()
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, authorization=authorization)
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_apikey_auth():
    authorization = AppSyncApiKeyAuthorization()
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, authorization=authorization)
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_iam_auth():
    authorization = AppSyncIAMAuthorization()
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, authorization=authorization)
    assert sample_transport.authorization is authorization

