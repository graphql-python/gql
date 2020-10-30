import logging

import pytest

from gql.cli import get_execute_args, get_parser, get_transport, get_transport_args


@pytest.fixture
def parser():
    return get_parser()


def test_cli_parser(parser):

    # Simple call with https server
    # gql-cli https://your_server.com
    args = parser.parse_args(["https://your_server.com"])

    assert args.server == "https://your_server.com"
    assert args.headers is None
    assert args.loglevel is None
    assert args.operation_name is None
    assert args.variables is None

    # Call with variable values parameters
    # gql-cli https://your_server.com --variables KEY1:value1 KEY2:value2
    args = parser.parse_args(
        ["https://your_server.com", "--variables", "KEY1:value1", "KEY2:value2"]
    )

    assert args.server == "https://your_server.com"
    assert args.variables == ["KEY1:value1", "KEY2:value2"]

    # Call with headers values parameters
    # gql-cli https://your_server.com --headers HEADER1:value1 HEADER2:value2
    args = parser.parse_args(
        ["https://your_server.com", "--headers", "HEADER1:value1", "HEADER2:value2"]
    )

    assert args.server == "https://your_server.com"
    assert args.headers == ["HEADER1:value1", "HEADER2:value2"]

    # Call with header value with a space in value
    # gql-cli https://your_server.com --headers Authorization:"Bearer blahblah"
    args = parser.parse_args(
        ["https://your_server.com", "--headers", "Authorization:Bearer blahblah"]
    )

    assert args.server == "https://your_server.com"
    assert args.headers == ["Authorization:Bearer blahblah"]

    # Check loglevel flags
    # gql-cli https://your_server.com --debug
    args = parser.parse_args(["https://your_server.com", "--debug"])
    assert args.loglevel == logging.DEBUG

    # gql-cli https://your_server.com --verbose
    args = parser.parse_args(["https://your_server.com", "--verbose"])

    assert args.loglevel == logging.INFO

    # Check operation_name
    # gql-cli https://your_server.com --operation-name my_operation
    args = parser.parse_args(
        ["https://your_server.com", "--operation-name", "my_operation"]
    )
    assert args.operation_name == "my_operation"


def test_cli_parse_headers(parser):

    args = parser.parse_args(
        [
            "https://your_server.com",
            "--headers",
            "Token1:1234",
            "Token2:5678",
            "TokenWithSpace:abc def",
            "TokenWithColon:abc:def",
        ]
    )

    transport_args = get_transport_args(args)

    expected_headers = {
        "Token1": "1234",
        "Token2": "5678",
        "TokenWithSpace": "abc def",
        "TokenWithColon": "abc:def",
    }

    assert transport_args == {"headers": expected_headers}


def test_cli_parse_headers_invalid_header(parser):

    args = parser.parse_args(
        ["https://your_server.com", "--headers", "TokenWithoutColon"]
    )

    with pytest.raises(ValueError):
        get_transport_args(args)


def test_cli_parse_operation_name(parser):

    args = parser.parse_args(["https://your_server.com", "--operation-name", "myop"])

    execute_args = get_execute_args(args)

    assert execute_args == {"operation_name": "myop"}


@pytest.mark.parametrize(
    "param",
    [
        {"args": ["key:abcdef"], "d": {"key": "abcdef"}},
        {"args": ['key:"abcdef"'], "d": {"key": "abcdef"}},
        {"args": ["key:1234"], "d": {"key": 1234}},
        {"args": ["key1:1234", "key2:5678"], "d": {"key1": 1234, "key2": 5678}},
        {"args": ["key1:null"], "d": {"key1": None}},
        {"args": ["key1:true"], "d": {"key1": True}},
        {"args": ["key1:false"], "d": {"key1": False}},
        {
            "args": ["key1:null", "key2:abcd", "key3:5"],
            "d": {"key1": None, "key2": "abcd", "key3": 5},
        },
    ],
)
def test_cli_parse_variable_value(parser, param):

    args = parser.parse_args(["https://your_server.com", "--variables", *param["args"]])

    execute_args = get_execute_args(args)

    expected_variable_values = param["d"]

    assert execute_args == {"variable_values": expected_variable_values}


@pytest.mark.parametrize("param", ["nocolon", 'key:"'])
def test_cli_parse_variable_value_invalid_param(parser, param):

    args = parser.parse_args(["https://your_server.com", "--variables", param])

    with pytest.raises(ValueError):
        get_execute_args(args)


@pytest.mark.aiohttp
@pytest.mark.parametrize(
    "url", ["http://your_server.com", "https://your_server.com"],
)
def test_cli_get_transport_aiohttp(parser, url):

    from gql.transport.aiohttp import AIOHTTPTransport

    args = parser.parse_args([url])

    transport = get_transport(args)

    assert isinstance(transport, AIOHTTPTransport)


@pytest.mark.websockets
@pytest.mark.parametrize(
    "url", ["ws://your_server.com", "wss://your_server.com"],
)
def test_cli_get_transport_websockets(parser, url):

    from gql.transport.websockets import WebsocketsTransport

    args = parser.parse_args([url])

    transport = get_transport(args)

    assert isinstance(transport, WebsocketsTransport)


def test_cli_get_transport_no_protocol(parser):

    args = parser.parse_args(["your_server.com"])

    with pytest.raises(ValueError):
        get_transport(args)
