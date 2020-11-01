import json
import logging
import sys
from argparse import ArgumentParser, Namespace, RawDescriptionHelpFormatter
from typing import Any, Dict

from graphql import GraphQLError
from yarl import URL

from gql import Client, __version__, gql
from gql.transport import AsyncTransport
from gql.transport.exceptions import TransportQueryError

description = """
Send GraphQL queries from the command line using http(s) or websockets.
If used interactively, write your query, then use Ctrl-D (EOF) to execute it.
"""

examples = """
EXAMPLES
========

# Simple query using https
echo 'query { continent(code:"AF") { name } }' | \
gql-cli https://countries.trevorblades.com

# Simple query using websockets
echo 'query { continent(code:"AF") { name } }' | \
gql-cli wss://countries.trevorblades.com/graphql

# Query with variable
echo 'query getContinent($code:ID!) { continent(code:$code) { name } }' | \
gql-cli https://countries.trevorblades.com --variables code:AF

# Interactive usage (insert your query in the terminal, then press Ctrl-D to execute it)
gql-cli wss://countries.trevorblades.com/graphql --variables code:AF

# Execute query saved in a file
cat query.gql | gql-cli wss://countries.trevorblades.com/graphql

"""


def get_parser(with_examples: bool = False) -> ArgumentParser:
    """Provides an ArgumentParser for the gql-cli script.

    This function is also used by sphinx to generate the script documentation.

    :param with_examples: set to False by default so that the examples are not
                          present in the sphinx docs (they are put there with
                          a different layout)
    """

    parser = ArgumentParser(
        description=description,
        epilog=examples if with_examples else None,
        formatter_class=RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "server", help="the server url starting with http://, https://, ws:// or wss://"
    )
    parser.add_argument(
        "-V",
        "--variables",
        nargs="*",
        help="query variables in the form key:json_value",
    )
    parser.add_argument(
        "-H", "--headers", nargs="*", help="http headers in the form key:value"
    )
    parser.add_argument("--version", action="version", version=f"v{__version__}")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-d",
        "--debug",
        help="print lots of debugging statements (loglevel==DEBUG)",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
    )
    group.add_argument(
        "-v",
        "--verbose",
        help="show low level messages (loglevel==INFO)",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    parser.add_argument(
        "-o",
        "--operation-name",
        help="set the operation_name value",
        dest="operation_name",
    )

    return parser


def get_transport_args(args: Namespace) -> Dict[str, Any]:
    """Extract extra arguments necessary for the transport
    from the parsed command line args

    Will create a headers dict by splitting the colon
    in the --headers arguments

    :param args: parsed command line arguments
    """

    transport_args: Dict[str, Any] = {}

    # Parse the headers argument
    headers = {}
    if args.headers is not None:
        for header in args.headers:

            try:
                # Split only the first colon (throw a ValueError if no colon is present)
                header_key, header_value = header.split(":", 1)

                headers[header_key] = header_value

            except ValueError:
                raise ValueError(f"Invalid header: {header}")

    if args.headers is not None:
        transport_args["headers"] = headers

    return transport_args


def get_execute_args(args: Namespace) -> Dict[str, Any]:
    """Extract extra arguments necessary for the execute or subscribe
    methods from the parsed command line args

    Extract the operation_name

    Extract the variable_values from the --variables argument
    by splitting the first colon, then loads the json value,
    We try to add double quotes around the value if it does not work first
    in order to simplify the passing of simple string values
    (we allow --variables KEY:VALUE instead of KEY:\"VALUE\")

    :param args: parsed command line arguments
    """

    execute_args: Dict[str, Any] = {}

    # Parse the operation_name argument
    if args.operation_name is not None:
        execute_args["operation_name"] = args.operation_name

    # Parse the variables argument
    if args.variables is not None:

        variables = {}

        for var in args.variables:

            try:
                # Split only the first colon
                # (throw a ValueError if no colon is present)
                variable_key, variable_json_value = var.split(":", 1)

                # Extract the json value,
                # trying with double quotes if it does not work
                try:
                    variable_value = json.loads(variable_json_value)
                except json.JSONDecodeError:
                    try:
                        variable_value = json.loads(f'"{variable_json_value}"')
                    except json.JSONDecodeError:
                        raise ValueError

                # Save the value in the variables dict
                variables[variable_key] = variable_value

            except ValueError:
                raise ValueError(f"Invalid variable: {var}")

        execute_args["variable_values"] = variables

    return execute_args


def get_transport(args: Namespace) -> AsyncTransport:
    """Instanciate a transport from the parsed command line arguments

    :param args: parsed command line arguments
    """

    # Get the url scheme from server parameter
    url = URL(args.server)
    scheme = url.scheme

    # Get extra transport parameters from command line arguments
    # (headers)
    transport_args = get_transport_args(args)

    # Instanciate transport depending on url scheme
    transport: AsyncTransport
    if scheme in ["ws", "wss"]:
        from gql.transport.websockets import WebsocketsTransport

        transport = WebsocketsTransport(
            url=args.server, ssl=(scheme == "wss"), **transport_args
        )
    elif scheme in ["http", "https"]:
        from gql.transport.aiohttp import AIOHTTPTransport

        transport = AIOHTTPTransport(url=args.server, **transport_args)
    else:
        raise ValueError("URL protocol should be one of: http, https, ws, wss")

    return transport


async def main(args: Namespace) -> int:
    """Main entrypoint of the gql-cli script

    :param args: The parsed command line arguments
    :return: The script exit code (0 = ok, 1 = error)
    """

    # Set requested log level
    if args.loglevel is not None:
        logging.basicConfig(level=args.loglevel)

    try:
        # Instanciate transport from command line arguments
        transport = get_transport(args)

        # Get extra execute parameters from command line arguments
        # (variables, operation_name)
        execute_args = get_execute_args(args)

    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # By default, the exit_code is 0 (everything is ok)
    exit_code = 0

    # Connect to the backend and provide a session
    async with Client(transport=transport) as session:

        while True:

            # Read multiple lines from input and trim whitespaces
            # Will read until EOF character is received (Ctrl-D)
            query_str = sys.stdin.read().strip()

            # Exit if query is empty
            if len(query_str) == 0:
                break

            # Parse query, continue on error
            try:
                query = gql(query_str)
            except GraphQLError as e:
                print(e, file=sys.stderr)
                exit_code = 1
                continue

            # Execute or Subscribe the query depending on transport
            try:
                try:
                    async for result in session.subscribe(query, **execute_args):
                        print(json.dumps(result))
                except KeyboardInterrupt:  # pragma: no cover
                    pass
                except NotImplementedError:
                    result = await session.execute(query, **execute_args)
                    print(json.dumps(result))
            except (GraphQLError, TransportQueryError) as e:
                print(e, file=sys.stderr)
                exit_code = 1

    return exit_code
