import argparse
import asyncio
import json
import logging
import sys

from graphql import GraphQLError
from yarl import URL

from gql import Client, __version__, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from gql.transport.websockets import WebsocketsTransport

description = """
Send GraphQL queries from the command line using http(s) or websockets.
If used interactively, write your query, then use Ctrl-D (EOF) to execute it.

USAGE
=====
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
gql-cli https://countries.trevorblades.com --params code:AF

# Interactive usage (insert your query in the terminal, then press Ctrl-D to execute it)
gql-cli wss://countries.trevorblades.com/graphql --params code:AF

# Execute query saved in a file
cat query.gql | gql-cli wss://countries.trevorblades.com/graphql

"""

def get_parser():
    parser = argparse.ArgumentParser(
        description=description,
        epilog=examples,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "server", help="the server url starting with http://, https://, ws:// or wss://"
    )
    parser.add_argument(
        "-p", "--params", nargs="*", help="query parameters in the form param:json_value"
    )
    parser.add_argument(
        "-H", "--headers", nargs="*", help="http headers in the form key:value"
    )
    parser.add_argument("--version", action="version", version=f"v{__version__}")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-d",
        "--debug",
        help="print lots of debugging statements",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    group.add_argument(
        "-v",
        "--verbose",
        help="show low level messages",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )
    parser.add_argument(
        "-o", "--operation-name", help="set the operation_name value", dest="operation_name"
    )

    return parser

def run_gql_cli(args):

    logging.basicConfig(level=args.loglevel)


    async def main():

        # Parse the params argument
        params = {}
        if args.params is not None:
            for p in args.params:

                try:
                    # Split only the first colon (throw a ValueError if no colon is present)
                    param_key, param_json_value = p.split(":", 1)

                    # Extract the json value, trying with double quotes if it does not work
                    try:
                        param_value = json.loads(param_json_value)
                    except json.JSONDecodeError:
                        try:
                            param_value = json.loads(f'"{param_json_value}"')
                        except json.JSONDecodeError:
                            raise ValueError

                    # Save the value in the params dict
                    params[param_key] = param_value

                except ValueError:
                    print(f"Invalid parameter: {p}", file=sys.stderr)
                    return 1

        # Parse the headers argument
        headers = {}
        if args.headers is not None:
            for header in args.headers:

                try:
                    # Split only the first colon (throw a ValueError if no colon is present)
                    header_key, header_value = header.split(":", 1)

                    headers[header_key] = header_value

                except ValueError:
                    print(f"Invalid header: {header}", file=sys.stderr)
                    return 1

        # Get the url scheme from server parameter
        url = URL(args.server)
        scheme = url.scheme

        # Get extra transport parameters from command line arguments
        transport_params = {}
        if args.headers is not None:
            transport_params["headers"] = headers

        # Instanciate transport depending on url scheme
        if scheme in ["ws", "wss"]:
            transport = WebsocketsTransport(
                url=args.server, ssl=(scheme == "wss"), **transport_params
            )
        elif scheme in ["http", "https"]:
            transport = AIOHTTPTransport(url=args.server, **transport_params)
        else:
            raise ValueError("URL protocol should be one of: http, https, ws, wss")

        # Get extra execution parameters from command line arguments
        extra_params = {}

        if args.params is not None:
            extra_params["variable_values"] = params

        if args.operation_name is not None:
            extra_params["operation_name"] = args.operation_name

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
                    continue

                # Execute or Subscribe the query depending on transport
                try:
                    if scheme in ["ws", "wss"]:
                        try:
                            async for result in session.subscribe(query, **extra_params):
                                print(result)
                        except KeyboardInterrupt:
                            pass
                    else:
                        result = await session.execute(query, **extra_params)
                        print(result)
                except TransportQueryError as e:
                    print(e)
                    pass


    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
