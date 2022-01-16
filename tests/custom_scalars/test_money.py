import asyncio
from math import isfinite
from typing import Any, Dict, NamedTuple, Optional

import pytest
from graphql import graphql_sync
from graphql.error import GraphQLError
from graphql.language import ValueNode
from graphql.pyutils import inspect
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLFloat,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.utilities import value_from_ast_untyped

from gql import Client, gql
from gql.transport.exceptions import TransportQueryError
from gql.utilities import serialize_value, update_schema_scalar, update_schema_scalars

from ..conftest import MS

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp


class Money(NamedTuple):
    amount: float
    currency: str


def is_finite(value: Any) -> bool:
    """Return true if a value is a finite number."""
    return (isinstance(value, int) and not isinstance(value, bool)) or (
        isinstance(value, float) and isfinite(value)
    )


def serialize_money(output_value: Any) -> Dict[str, Any]:
    if not isinstance(output_value, Money):
        raise GraphQLError("Cannot serialize money value: " + inspect(output_value))
    return output_value._asdict()


def parse_money_value(input_value: Any) -> Money:
    """Using Money custom scalar from graphql-core tests except here the
    input value is supposed to be a dict instead of a Money object."""

    """
    if isinstance(input_value, Money):
        return input_value
    """

    if isinstance(input_value, dict):
        amount = input_value.get("amount", None)
        currency = input_value.get("currency", None)

        if not is_finite(amount) or not isinstance(currency, str):
            raise GraphQLError("Cannot parse money value dict: " + inspect(input_value))

        return Money(float(amount), currency)
    else:
        raise GraphQLError("Cannot parse money value: " + inspect(input_value))


def parse_money_literal(
    value_node: ValueNode, variables: Optional[Dict[str, Any]] = None
) -> Money:
    money = value_from_ast_untyped(value_node, variables)
    if variables is not None and (
        # variables are not set when checked with ValuesIOfCorrectTypeRule
        not money
        or not is_finite(money.get("amount"))
        or not isinstance(money.get("currency"), str)
    ):
        raise GraphQLError("Cannot parse literal money value: " + inspect(money))
    return Money(**money)


MoneyScalar = GraphQLScalarType(
    name="Money",
    serialize=serialize_money,
    parse_value=parse_money_value,
    parse_literal=parse_money_literal,
)

root_value = {
    "balance": Money(42, "DM"),
    "friends_balance": [Money(12, "EUR"), Money(24, "EUR"), Money(150, "DM")],
    "countries_balance": {
        "Belgium": Money(15000, "EUR"),
        "Luxembourg": Money(99999, "EUR"),
    },
}


def resolve_balance(root, _info):
    return root["balance"]


def resolve_friends_balance(root, _info):
    return root["friends_balance"]


def resolve_countries_balance(root, _info):
    return root["countries_balance"]


def resolve_belgium_balance(countries_balance, _info):
    return countries_balance["Belgium"]


def resolve_luxembourg_balance(countries_balance, _info):
    return countries_balance["Luxembourg"]


def resolve_to_euros(_root, _info, money):
    amount = money.amount
    currency = money.currency
    if not amount or currency == "EUR":
        return amount
    if currency == "DM":
        return amount * 0.5
    raise ValueError("Cannot convert to euros: " + inspect(money))


countriesBalance = GraphQLObjectType(
    name="CountriesBalance",
    fields={
        "Belgium": GraphQLField(
            GraphQLNonNull(MoneyScalar), resolve=resolve_belgium_balance
        ),
        "Luxembourg": GraphQLField(
            GraphQLNonNull(MoneyScalar), resolve=resolve_luxembourg_balance
        ),
    },
)

queryType = GraphQLObjectType(
    name="RootQueryType",
    fields={
        "balance": GraphQLField(MoneyScalar, resolve=resolve_balance),
        "toEuros": GraphQLField(
            GraphQLFloat,
            args={"money": GraphQLArgument(MoneyScalar)},
            resolve=resolve_to_euros,
        ),
        "friends_balance": GraphQLField(
            GraphQLList(MoneyScalar), resolve=resolve_friends_balance
        ),
        "countries_balance": GraphQLField(
            GraphQLNonNull(countriesBalance), resolve=resolve_countries_balance,
        ),
    },
)


def resolve_spent_money(spent_money, _info, **kwargs):
    return spent_money


async def subscribe_spend_all(_root, _info, money):
    while money.amount > 0:
        money = Money(money.amount - 1, money.currency)
        yield money
        await asyncio.sleep(1 * MS)


subscriptionType = GraphQLObjectType(
    "Subscription",
    fields=lambda: {
        "spend": GraphQLField(
            MoneyScalar,
            args={"money": GraphQLArgument(MoneyScalar)},
            subscribe=subscribe_spend_all,
            resolve=resolve_spent_money,
        )
    },
)

schema = GraphQLSchema(query=queryType, subscription=subscriptionType,)


def test_custom_scalar_in_output():

    client = Client(schema=schema, parse_results=True)

    query = gql("{balance}")

    result = client.execute(query, root_value=root_value)

    print(result)

    assert result["balance"] == root_value["balance"]


def test_custom_scalar_in_output_embedded_fragments():

    client = Client(schema=schema, parse_results=True)

    query = gql(
        """
        fragment LuxMoneyInternal on CountriesBalance {
            ... on CountriesBalance {
                Luxembourg
            }
        }
        query {
            countries_balance {
                Belgium
                ...LuxMoney
            }
        }
        fragment LuxMoney on CountriesBalance {
            ...LuxMoneyInternal
        }
        """
    )

    result = client.execute(query, root_value=root_value)

    print(result)

    belgium_money = result["countries_balance"]["Belgium"]
    assert belgium_money == Money(15000, "EUR")
    luxembourg_money = result["countries_balance"]["Luxembourg"]
    assert luxembourg_money == Money(99999, "EUR")


def test_custom_scalar_list_in_output():

    client = Client(schema=schema, parse_results=True)

    query = gql("{friends_balance}")

    result = client.execute(query, root_value=root_value)

    print(result)

    assert result["friends_balance"] == root_value["friends_balance"]


def test_custom_scalar_in_input_query():

    client = Client(schema=schema)

    query = gql('{toEuros(money: {amount: 10, currency: "DM"})}')

    result = client.execute(query, root_value=root_value)

    assert result["toEuros"] == 5

    query = gql('{toEuros(money: {amount: 10, currency: "EUR"})}')

    result = client.execute(query, root_value=root_value)

    assert result["toEuros"] == 10


def test_custom_scalar_in_input_variable_values():

    client = Client(schema=schema)

    query = gql("query myquery($money: Money) {toEuros(money: $money)}")

    money_value = {"amount": 10, "currency": "DM"}

    variable_values = {"money": money_value}

    result = client.execute(
        query, variable_values=variable_values, root_value=root_value
    )

    assert result["toEuros"] == 5


def test_custom_scalar_in_input_variable_values_serialized():

    client = Client(schema=schema)

    query = gql("query myquery($money: Money) {toEuros(money: $money)}")

    money_value = Money(10, "DM")

    variable_values = {"money": money_value}

    result = client.execute(
        query,
        variable_values=variable_values,
        root_value=root_value,
        serialize_variables=True,
    )

    assert result["toEuros"] == 5


def test_custom_scalar_in_input_variable_values_serialized_with_operation_name():

    client = Client(schema=schema)

    query = gql("query myquery($money: Money) {toEuros(money: $money)}")

    money_value = Money(10, "DM")

    variable_values = {"money": money_value}

    result = client.execute(
        query,
        variable_values=variable_values,
        root_value=root_value,
        serialize_variables=True,
        operation_name="myquery",
    )

    assert result["toEuros"] == 5


def test_serialize_variable_values_exception_multiple_ops_without_operation_name():

    client = Client(schema=schema)

    query = gql(
        """
    query myconversion($money: Money) {
        toEuros(money: $money)
    }

    query mybalance {
        balance
    }"""
    )

    money_value = Money(10, "DM")

    variable_values = {"money": money_value}

    with pytest.raises(GraphQLError) as exc_info:
        client.execute(
            query,
            variable_values=variable_values,
            root_value=root_value,
            serialize_variables=True,
        )

    exception = exc_info.value

    assert (
        str(exception)
        == "Must provide operation name if query contains multiple operations."
    )


def test_serialize_variable_values_exception_operation_name_not_found():

    client = Client(schema=schema)

    query = gql(
        """
    query myconversion($money: Money) {
        toEuros(money: $money)
    }
"""
    )

    money_value = Money(10, "DM")

    variable_values = {"money": money_value}

    with pytest.raises(GraphQLError) as exc_info:
        client.execute(
            query,
            variable_values=variable_values,
            root_value=root_value,
            serialize_variables=True,
            operation_name="invalid_operation_name",
        )

    exception = exc_info.value

    assert str(exception) == "Unknown operation named 'invalid_operation_name'."


def test_custom_scalar_subscribe_in_input_variable_values_serialized():

    client = Client(schema=schema)

    query = gql("subscription spendAll($money: Money) {spend(money: $money)}")

    money_value = Money(10, "DM")

    variable_values = {"money": money_value}

    expected_result = {"spend": Money(10, "DM")}

    for result in client.subscribe(
        query,
        variable_values=variable_values,
        root_value=root_value,
        serialize_variables=True,
        parse_result=True,
    ):
        print(f"result = {result!r}")
        assert isinstance(result["spend"], Money)
        expected_result["spend"] = Money(expected_result["spend"].amount - 1, "DM")
        assert expected_result == result


async def make_money_backend(aiohttp_server):
    from aiohttp import web

    async def handler(request):
        data = await request.json()
        source = data["query"]

        try:
            variables = data["variables"]
        except KeyError:
            variables = None

        result = graphql_sync(
            schema, source, variable_values=variables, root_value=root_value
        )

        return web.json_response(
            {
                "data": result.data,
                "errors": [str(e) for e in result.errors] if result.errors else None,
            }
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    return server


async def make_money_transport(aiohttp_server):
    from gql.transport.aiohttp import AIOHTTPTransport

    server = await make_money_backend(aiohttp_server)

    url = server.make_url("/")

    transport = AIOHTTPTransport(url=url, timeout=10)

    return transport


async def make_sync_money_transport(aiohttp_server):
    from gql.transport.requests import RequestsHTTPTransport

    server = await make_money_backend(aiohttp_server)

    url = server.make_url("/")

    transport = RequestsHTTPTransport(url=url, timeout=10)

    return (server, transport)


@pytest.mark.asyncio
async def test_custom_scalar_in_output_with_transport(event_loop, aiohttp_server):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport,) as session:

        query = gql("{balance}")

        result = await session.execute(query)

        print(result)

        assert result["balance"] == serialize_money(root_value["balance"])


@pytest.mark.asyncio
async def test_custom_scalar_in_input_query_with_transport(event_loop, aiohttp_server):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport,) as session:

        query = gql('{toEuros(money: {amount: 10, currency: "DM"})}')

        result = await session.execute(query)

        assert result["toEuros"] == 5

        query = gql('{toEuros(money: {amount: 10, currency: "EUR"})}')

        result = await session.execute(query)

        assert result["toEuros"] == 10


@pytest.mark.asyncio
async def test_custom_scalar_in_input_variable_values_with_transport(
    event_loop, aiohttp_server
):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport,) as session:

        query = gql("query myquery($money: Money) {toEuros(money: $money)}")

        money_value = {"amount": 10, "currency": "DM"}
        # money_value = Money(10, "DM")

        variable_values = {"money": money_value}

        result = await session.execute(query, variable_values=variable_values)

        print(f"result = {result!r}")
        assert result["toEuros"] == 5


@pytest.mark.asyncio
async def test_custom_scalar_in_input_variable_values_split_with_transport(
    event_loop, aiohttp_server
):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport,) as session:

        query = gql(
            """
query myquery($amount: Float, $currency: String) {
    toEuros(money: {amount: $amount, currency: $currency})
}"""
        )

        variable_values = {"amount": 10, "currency": "DM"}

        result = await session.execute(query, variable_values=variable_values)

        print(f"result = {result!r}")
        assert result["toEuros"] == 5


@pytest.mark.asyncio
async def test_custom_scalar_serialize_variables(event_loop, aiohttp_server):

    transport = await make_money_transport(aiohttp_server)

    async with Client(schema=schema, transport=transport,) as session:

        query = gql("query myquery($money: Money) {toEuros(money: $money)}")

        variable_values = {"money": Money(10, "DM")}

        result = await session.execute(
            query, variable_values=variable_values, serialize_variables=True
        )

        print(f"result = {result!r}")
        assert result["toEuros"] == 5


@pytest.mark.asyncio
async def test_custom_scalar_serialize_variables_no_schema(event_loop, aiohttp_server):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport,) as session:

        query = gql("query myquery($money: Money) {toEuros(money: $money)}")

        variable_values = {"money": Money(10, "DM")}

        with pytest.raises(TransportQueryError):
            await session.execute(
                query, variable_values=variable_values, serialize_variables=True
            )


@pytest.mark.asyncio
async def test_custom_scalar_serialize_variables_schema_from_introspection(
    event_loop, aiohttp_server
):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:

        schema = session.client.schema

        # Updating the Money Scalar in the schema
        # We cannot replace it because some other objects keep a reference
        # to the existing Scalar
        # cannot do: schema.type_map["Money"] = MoneyScalar

        money_scalar = schema.type_map["Money"]

        money_scalar.serialize = MoneyScalar.serialize
        money_scalar.parse_value = MoneyScalar.parse_value
        money_scalar.parse_literal = MoneyScalar.parse_literal

        query = gql("query myquery($money: Money) {toEuros(money: $money)}")

        variable_values = {"money": Money(10, "DM")}

        result = await session.execute(
            query, variable_values=variable_values, serialize_variables=True
        )

        print(f"result = {result!r}")
        assert result["toEuros"] == 5


@pytest.mark.asyncio
async def test_update_schema_scalars(event_loop, aiohttp_server):

    transport = await make_money_transport(aiohttp_server)

    async with Client(transport=transport, fetch_schema_from_transport=True) as session:

        # Update the schema MoneyScalar default implementation from
        # introspection with our provided conversion methods
        # update_schema_scalars(session.client.schema, [MoneyScalar])
        update_schema_scalar(session.client.schema, "Money", MoneyScalar)

        query = gql("query myquery($money: Money) {toEuros(money: $money)}")

        variable_values = {"money": Money(10, "DM")}

        result = await session.execute(
            query, variable_values=variable_values, serialize_variables=True
        )

        print(f"result = {result!r}")
        assert result["toEuros"] == 5


def test_update_schema_scalars_invalid_scalar():

    with pytest.raises(TypeError) as exc_info:
        update_schema_scalars(schema, [int])

    exception = exc_info.value

    assert str(exception) == "Scalars should be instances of GraphQLScalarType."

    with pytest.raises(TypeError) as exc_info:
        update_schema_scalar(schema, "test", int)

    exception = exc_info.value

    assert str(exception) == "Scalars should be instances of GraphQLScalarType."


def test_update_schema_scalars_invalid_scalar_argument():

    with pytest.raises(TypeError) as exc_info:
        update_schema_scalars(schema, MoneyScalar)

    exception = exc_info.value

    assert str(exception) == "Scalars argument should be a list of scalars."


def test_update_schema_scalars_scalar_not_found_in_schema():

    NotFoundScalar = GraphQLScalarType(name="abcd",)

    with pytest.raises(KeyError) as exc_info:
        update_schema_scalars(schema, [MoneyScalar, NotFoundScalar])

    exception = exc_info.value

    assert "Scalar 'abcd' not found in schema." in str(exception)


def test_update_schema_scalars_scalar_type_is_not_a_scalar_in_schema():

    with pytest.raises(TypeError) as exc_info:
        update_schema_scalar(schema, "CountriesBalance", MoneyScalar)

    exception = exc_info.value

    assert 'The type "CountriesBalance" is not a GraphQLScalarType, it is a' in str(
        exception
    )


@pytest.mark.asyncio
@pytest.mark.requests
async def test_custom_scalar_serialize_variables_sync_transport(
    event_loop, aiohttp_server, run_sync_test
):

    server, transport = await make_sync_money_transport(aiohttp_server)

    def test_code():
        with Client(schema=schema, transport=transport, parse_results=True) as session:

            query = gql("query myquery($money: Money) {toEuros(money: $money)}")

            variable_values = {"money": Money(10, "DM")}

            result = session.execute(
                query, variable_values=variable_values, serialize_variables=True
            )

            print(f"result = {result!r}")
            assert result["toEuros"] == 5

    await run_sync_test(event_loop, server, test_code)


def test_serialize_value_with_invalid_type():

    with pytest.raises(GraphQLError) as exc_info:
        serialize_value("Not a valid type", 50)

    exception = exc_info.value

    assert (
        str(exception) == "Impossible to serialize value with type: 'Not a valid type'."
    )


def test_serialize_value_with_non_null_type_null():

    non_null_int = GraphQLNonNull(GraphQLInt)

    with pytest.raises(GraphQLError) as exc_info:
        serialize_value(non_null_int, None)

    exception = exc_info.value

    assert str(exception) == "Type Int! Cannot be None."


def test_serialize_value_with_nullable_type():

    nullable_int = GraphQLInt

    assert serialize_value(nullable_int, None) is None


@pytest.mark.asyncio
async def test_gql_cli_print_schema(event_loop, aiohttp_server, capsys):

    from gql.cli import get_parser, main

    server = await make_money_backend(aiohttp_server)

    url = str(server.make_url("/"))

    parser = get_parser(with_examples=True)
    args = parser.parse_args([url, "--print-schema"])

    exit_code = await main(args)

    assert exit_code == 0

    # Check that the result has been printed on stdout
    captured = capsys.readouterr()
    captured_out = str(captured.out).strip()

    print(captured_out)
    assert (
        """
type Subscription {
  spend(money: Money): Money
}
""".strip()
        in captured_out
    )
