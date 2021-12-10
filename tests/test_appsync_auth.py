import pytest

mock_transport_host = "appsyncapp.awsgateway.com.example.org"
mock_transport_url = f"https://{mock_transport_host}/graphql"


@pytest.mark.botocore
def test_appsync_init_with_minimal_args(fake_session_factory):
    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    sample_transport = AppSyncWebsocketsTransport(
        url=mock_transport_url, session=fake_session_factory()
    )
    assert isinstance(sample_transport.auth, AppSyncIAMAuthentication)
    assert sample_transport.connect_timeout == 10
    assert sample_transport.close_timeout == 10
    assert sample_transport.ack_timeout == 10
    assert sample_transport.ssl is False
    assert sample_transport.connect_args == {}


@pytest.mark.botocore
def test_appsync_init_with_no_credentials(caplog, fake_session_factory):
    import botocore.exceptions
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    with pytest.raises(botocore.exceptions.NoCredentialsError):
        sample_transport = AppSyncWebsocketsTransport(
            url=mock_transport_url, session=fake_session_factory(credentials=None),
        )
        assert sample_transport.auth is None

    expected_error = "Credentials not found"

    print(f"Captured log: {caplog.text}")

    assert expected_error in caplog.text


@pytest.mark.websockets
def test_appsync_init_with_jwt_auth():
    from gql.transport.appsync_auth import AppSyncJWTAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    auth = AppSyncJWTAuthentication(host=mock_transport_host, jwt="some-jwt")
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)
    assert sample_transport.auth is auth

    assert auth.get_headers() == {
        "host": mock_transport_host,
        "Authorization": "some-jwt",
    }


@pytest.mark.websockets
def test_appsync_init_with_apikey_auth():
    from gql.transport.appsync_auth import AppSyncApiKeyAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    auth = AppSyncApiKeyAuthentication(host=mock_transport_host, api_key="some-api-key")
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)
    assert sample_transport.auth is auth

    assert auth.get_headers() == {
        "host": mock_transport_host,
        "x-api-key": "some-api-key",
    }


@pytest.mark.botocore
def test_appsync_init_with_iam_auth_without_creds(fake_session_factory):
    import botocore.exceptions
    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    auth = AppSyncIAMAuthentication(
        host=mock_transport_host, session=fake_session_factory(credentials=None),
    )
    with pytest.raises(botocore.exceptions.NoCredentialsError):
        AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)


@pytest.mark.botocore
def test_appsync_init_with_iam_auth_with_creds(fake_credentials_factory):
    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

    auth = AppSyncIAMAuthentication(
        host=mock_transport_host,
        credentials=fake_credentials_factory(),
        region_name="us-east-1",
    )
    sample_transport = AppSyncWebsocketsTransport(url=mock_transport_url, auth=auth)
    assert sample_transport.auth is auth


@pytest.mark.botocore
def test_appsync_init_with_iam_auth_and_no_region(
    caplog, fake_credentials_factory, fake_session_factory
):
    """

    WARNING: this test will fail if:
     - you have a default region set in ~/.aws/config
     - you have the AWS_DEFAULT_REGION environment variable set

     """
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport
    from botocore.exceptions import NoRegionError
    import logging

    caplog.set_level(logging.WARNING)

    with pytest.raises(NoRegionError):
        session = fake_session_factory(credentials=fake_credentials_factory())
        session._region_name = None
        session._credentials.region = None
        transport = AppSyncWebsocketsTransport(url=mock_transport_url, session=session)

        # prints the region name in case the test fails
        print(f"Region found: {transport.auth._region_name}")

    print(f"Captured: {caplog.text}")

    expected_error = (
        "Region name not found. "
        "It was not possible to detect your region either from the host "
        "or from your default AWS configuration."
    )

    assert expected_error in caplog.text


@pytest.mark.botocore
def test_munge_url(fake_signer_factory, fake_request_factory):
    from gql.transport.appsync_auth import AppSyncIAMAuthentication
    from gql.transport.appsync_websockets import AppSyncWebsocketsTransport

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


@pytest.mark.botocore
def test_munge_url_format(
    fake_signer_factory,
    fake_request_factory,
    fake_credentials_factory,
    fake_session_factory,
):
    from gql.transport.appsync_auth import AppSyncIAMAuthentication

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
