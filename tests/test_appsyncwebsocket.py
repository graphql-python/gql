import botocore.exceptions
import pytest

from gql.transport.awsappsyncwebsocket import (
    AppSyncApiKeyAuthorization,
    AppSyncIAMAuthorization,
    AppSyncOIDCAuthorization,
    AppSyncWebsocketsTransport,
    MissingRegionError,
)

mock_transport_url = "https://appsyncapp.awsgateway.com.example.org"


def test_appsyncwebsocket_init_with_minimal_args(fake_session_factory):
    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, session=fake_session_factory()
    )
    assert isinstance(sample_transport.authorization, AppSyncIAMAuthorization)
    assert sample_transport.connect_timeout == 10
    assert sample_transport.close_timeout == 10
    assert sample_transport.ack_timeout == 10
    assert sample_transport.ssl is False
    assert sample_transport.connect_args == {}


def test_appsyncwebsocket_init_with_no_credentials(
    fake_session_factory, fake_logger_factory
):
    fake_logger = fake_logger_factory()
    with pytest.raises(botocore.exceptions.NoCredentialsError):
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url,
            session=fake_session_factory(credentials=None),
            logger=fake_logger,
        )
        assert sample_transport.authorization is None
        assert fake_logger._messages.length > 0
        assert "credentials" in fake_logger._messages[0].lower()


def test_appsyncwebsocket_init_with_oidc_auth():
    authorization = AppSyncOIDCAuthorization(host=mock_transport_url, jwt="some-jwt")
    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, authorization=authorization
    )
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_apikey_auth():
    authorization = AppSyncApiKeyAuthorization(
        host=mock_transport_url, api_key="some-api-key"
    )
    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, authorization=authorization
    )
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_iam_auth_without_creds():
    authorization = AppSyncIAMAuthorization(host=mock_transport_url, credentials=None)
    with pytest.raises(botocore.exceptions.NoCredentialsError):
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url, authorization=authorization
        )


def test_appsyncwebsocket_init_with_iam_auth_with_creds(fake_credentials_factory):
    authorization = AppSyncIAMAuthorization(
        host=mock_transport_url,
        credentials=fake_credentials_factory(),
        region_name="us-east-1",
    )
    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, authorization=authorization
    )
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_iam_auth_and_no_region(
    fake_credentials_factory, fake_logger_factory
):
    fake_logger = fake_logger_factory()
    with pytest.raises(MissingRegionError):
        authorization = AppSyncIAMAuthorization(
            host=mock_transport_url, credentials=fake_credentials_factory()
        )
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url, authorization=authorization, logger=fake_logger
        )
        assert sample_transport.authorization is None
        assert fake_logger._messages.length > 0
        assert "credentials" in fake_logger._messages[0].lower()


def test_munge_url(fake_signer_factory, fake_request_factory):
    test_url = "https://appsync-api.aws.example.org/some-other-params"

    authorization = AppSyncIAMAuthorization(
        host=test_url,
        signer=fake_signer_factory(),
        request_creator=fake_request_factory,
    )
    sample_transport = AppSyncWebsocketsTransport(
        url=test_url, authorization=authorization
    )

    expected_url = authorization.host_to_auth_url()
    assert sample_transport.url == expected_url


def test_munge_url_format(
    fake_signer_factory,
    fake_request_factory,
    fake_credentials_factory,
    fake_session_factory,
):
    test_url = "https://appsync-api.aws.example.org/some-other-params"

    authorization = AppSyncIAMAuthorization(
        host=test_url,
        signer=fake_signer_factory(),
        session=fake_session_factory(),
        request_creator=fake_request_factory,
        credentials=fake_credentials_factory(),
    )

    header_string = "eyJGYWtlQXV0aG9yaXphdGlvbiI6ImEiLCJGYWtlVGltZSI6InRvZGF5In0="
    expected_url = (
        f"wss://appsync-realtime-api.aws.example.org/"
        f"some-other-params?header={header_string}&payload=e30="
    )
    assert authorization.host_to_auth_url() == expected_url
