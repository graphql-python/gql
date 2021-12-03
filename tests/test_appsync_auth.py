import pytest

# Marking all tests in this file with the appsync marker
pytestmark = pytest.mark.appsync

mock_transport_host = "appsyncapp.awsgateway.com.example.org"
mock_transport_url = f"https://{mock_transport_host}/graphql"


def test_appsync_init_with_minimal_args(fake_session_factory):
    from gql.transport.appsync import (
        AppSyncIAMAuthentication,
        AppSyncWebsocketsTransport,
    )

    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, session=fake_session_factory()
    )
    assert isinstance(sample_transport.auth, AppSyncIAMAuthentication)
    assert sample_transport.connect_timeout == 10
    assert sample_transport.close_timeout == 10
    assert sample_transport.ack_timeout == 10
    assert sample_transport.ssl is False
    assert sample_transport.connect_args == {}


def test_appsync_init_with_no_credentials(caplog, fake_session_factory):
    import botocore.exceptions
    from gql.transport.appsync import AppSyncWebsocketsTransport

    with pytest.raises(botocore.exceptions.NoCredentialsError):
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url, session=fake_session_factory(credentials=None),
        )
        assert sample_transport.auth is None

    expected_error = "Credentials not found"

    print(f"Captured log: {caplog.text}")

    assert expected_error in caplog.text


def test_appsync_init_with_jwt_auth():
    from gql.transport.appsync import (
        AppSyncJWTAuthentication,
        AppSyncWebsocketsTransport,
    )

    auth = AppSyncJWTAuthentication(host=mock_transport_host, jwt="some-jwt")
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)
    assert sample_transport.auth is auth

    assert auth.get_headers() == {
        "host": mock_transport_host,
        "Authorization": "some-jwt",
    }


def test_appsync_init_with_apikey_auth():
    from gql.transport.appsync import (
        AppSyncApiKeyAuthentication,
        AppSyncWebsocketsTransport,
    )

    auth = AppSyncApiKeyAuthentication(host=mock_transport_host, api_key="some-api-key")
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)
    assert sample_transport.auth is auth

    assert auth.get_headers() == {
        "host": mock_transport_host,
        "x-api-key": "some-api-key",
    }


def test_appsync_init_with_iam_auth_without_creds(fake_session_factory):
    import botocore.exceptions
    from gql.transport.appsync import (
        AppSyncIAMAuthentication,
        AppSyncWebsocketsTransport,
    )

    auth = AppSyncIAMAuthentication(
        host=mock_transport_host, session=fake_session_factory(credentials=None),
    )
    with pytest.raises(botocore.exceptions.NoCredentialsError):
        AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)


def test_appsync_init_with_iam_auth_with_creds(fake_credentials_factory):
    from gql.transport.appsync import (
        AppSyncIAMAuthentication,
        AppSyncWebsocketsTransport,
    )

    auth = AppSyncIAMAuthentication(
        host=mock_transport_host,
        credentials=fake_credentials_factory(),
        region_name="us-east-1",
    )
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)
    assert sample_transport.auth is auth


def test_appsync_init_with_iam_auth_and_no_region(caplog, fake_credentials_factory):
    from gql.transport.appsync import (
        AppSyncIAMAuthentication,
        AppSyncWebsocketsTransport,
    )

    with pytest.raises(TypeError):
        auth = AppSyncIAMAuthentication(
            host=mock_transport_host, credentials=fake_credentials_factory()
        )
        AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)

        print(f"Region found: {auth._region_name}")

    print(f"Captured: {caplog.text}")

    expected_error = "the AWS region is missing from the credentials"

    assert expected_error in caplog.text


def test_munge_url(fake_signer_factory, fake_request_factory):
    from gql.transport.appsync import (
        AppSyncIAMAuthentication,
        AppSyncWebsocketsTransport,
    )

    test_url = "https://appsync-api.aws.example.org/some-other-params"

    auth = AppSyncIAMAuthentication(
        host=test_url,
        signer=fake_signer_factory(),
        request_creator=fake_request_factory,
    )
    sample_transport = AppSyncWebsocketsTransport(url=test_url, auth=auth)

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
    from gql.transport.appsync import AppSyncIAMAuthentication

    test_url = "https://appsync-api.aws.example.org/some-other-params"

    auth = AppSyncIAMAuthentication(
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
    assert auth.get_auth_url(test_url) == expected_url
