import pytest

# Marking all tests in this file with the appsyncwebsockets marker
pytestmark = pytest.mark.appsyncwebsockets

mock_transport_url = "https://appsyncapp.awsgateway.com.example.org"


def test_appsyncwebsocket_init_with_minimal_args(fake_session_factory):
    from gql.transport.awsappsync import (
        AppSyncIAMAuthorization,
        AppSyncWebsocketsTransport,
    )

    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, session=fake_session_factory()
    )
    assert isinstance(sample_transport.authorization, AppSyncIAMAuthorization)
    assert sample_transport.connect_timeout == 10
    assert sample_transport.close_timeout == 10
    assert sample_transport.ack_timeout == 10
    assert sample_transport.ssl is False
    assert sample_transport.connect_args == {}


def test_appsyncwebsocket_init_with_no_credentials(caplog, fake_session_factory):
    import botocore.exceptions
    from gql.transport.awsappsync import AppSyncWebsocketsTransport

    with pytest.raises(botocore.exceptions.NoCredentialsError):
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url, session=fake_session_factory(credentials=None),
        )
        assert sample_transport.authorization is None

    expected_error = "Credentials not found"

    print(f"Captured log: {caplog.text}")

    assert expected_error in caplog.text


def test_appsyncwebsocket_init_with_oidc_auth():
    from gql.transport.awsappsync import (
        AppSyncOIDCAuthorization,
        AppSyncWebsocketsTransport,
    )

    authorization = AppSyncOIDCAuthorization(host=mock_transport_url, jwt="some-jwt")
    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, authorization=authorization
    )
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_apikey_auth():
    from gql.transport.awsappsync import (
        AppSyncApiKeyAuthorization,
        AppSyncWebsocketsTransport,
    )

    authorization = AppSyncApiKeyAuthorization(
        host=mock_transport_url, api_key="some-api-key"
    )
    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, authorization=authorization
    )
    assert sample_transport.authorization is authorization


def test_appsyncwebsocket_init_with_iam_auth_without_creds(fake_session_factory):
    import botocore.exceptions
    from gql.transport.awsappsync import (
        AppSyncIAMAuthorization,
        AppSyncWebsocketsTransport,
    )

    authorization = AppSyncIAMAuthorization(
        host=mock_transport_url, session=fake_session_factory(credentials=None),
    )
    with pytest.raises(botocore.exceptions.NoCredentialsError):
        AppSyncWebsocketsTransport(url=mock_transport_url, authorization=authorization)


def test_appsyncwebsocket_init_with_iam_auth_with_creds(fake_credentials_factory):
    from gql.transport.awsappsync import (
        AppSyncIAMAuthorization,
        AppSyncWebsocketsTransport,
    )

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
    caplog, fake_credentials_factory
):
    from gql.transport.awsappsync import (
        AppSyncIAMAuthorization,
        AppSyncWebsocketsTransport,
    )

    with pytest.raises(TypeError):
        authorization = AppSyncIAMAuthorization(
            host=mock_transport_url, credentials=fake_credentials_factory()
        )
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url, authorization=authorization
        )
        assert sample_transport.authorization is None

    print(f"Captured: {caplog.text}")

    expected_error = "the AWS region is missing from the credentials"

    assert expected_error in caplog.text


def test_munge_url(fake_signer_factory, fake_request_factory):
    from gql.transport.awsappsync import (
        AppSyncIAMAuthorization,
        AppSyncWebsocketsTransport,
    )

    test_url = "https://appsync-api.aws.example.org/some-other-params"

    authorization = AppSyncIAMAuthorization(
        host=test_url,
        signer=fake_signer_factory(),
        request_creator=fake_request_factory,
    )
    sample_transport = AppSyncWebsocketsTransport(
        url=test_url, authorization=authorization
    )

    header_string = (
        "eyJGYWtlQXV0aG9yaXphdGlvbiI6ImEiLCJGYWtlVGltZSI6InRvZGF5"
        "IiwiaG9zdCI6Imh0dHBzOi8vYXBwc3luYy1hcGkuYXdzLmV4YW1wbGUu"
        "b3JnL3NvbWUtb3RoZXItcGFyYW1zIn0="
    )
    expected_url = (
        "wss://appsync-realtime-api.aws.example.org/"
        f"some-other-params?header={header_string}&payload=e30="
    )
    assert sample_transport.url == expected_url


def test_munge_url_format(
    fake_signer_factory,
    fake_request_factory,
    fake_credentials_factory,
    fake_session_factory,
):
    from gql.transport.awsappsync import AppSyncIAMAuthorization

    test_url = "https://appsync-api.aws.example.org/some-other-params"

    authorization = AppSyncIAMAuthorization(
        host=test_url,
        signer=fake_signer_factory(),
        session=fake_session_factory(),
        request_creator=fake_request_factory,
        credentials=fake_credentials_factory(),
    )

    header_string = (
        "eyJGYWtlQXV0aG9yaXphdGlvbiI6ImEiLCJGYWtlVGltZSI6InRvZGF5"
        "IiwiaG9zdCI6Imh0dHBzOi8vYXBwc3luYy1hcGkuYXdzLmV4YW1wbGUu"
        "b3JnL3NvbWUtb3RoZXItcGFyYW1zIn0="
    )
    expected_url = (
        "wss://appsync-realtime-api.aws.example.org/"
        f"some-other-params?header={header_string}&payload=e30="
    )
    assert authorization.get_auth_url(test_url) == expected_url
