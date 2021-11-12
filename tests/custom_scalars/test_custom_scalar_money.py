import asyncio
from typing import Any, Dict, NamedTuple, Optional

import pytest
from graphql import graphql_sync
from graphql.error import GraphQLError
from graphql.language import ValueNode
from graphql.pyutils import inspect, is_finite
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLFloat,
    GraphQLInt,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.utilities import value_from_ast_untyped

from gql import Client, gql
from gql.variable_values import serialize_value

from ..conftest import MS

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp


class Money(NamedTuple):
    amount: float
    currency: str


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


def resolve_balance(root, _info):
    return root


def resolve_to_euros(_root, _info, money):
    amount = money.amount
    currency = money.currency
    if not amount or currency == "EUR":
        return amount
    if currency == "DM":
        return amount * 0.5
    raise ValueError("Cannot convert to euros: " + inspect(money))


queryType = GraphQLObjectType(
    name="RootQueryType",
    fields={
        "balance": GraphQLField(MoneyScalar, resolve=resolve_balance),
        "toEuros": GraphQLField(
            GraphQLFloat,
            args={"money": GraphQLArgument(MoneyScalar)},
            resolve=resolve_to_euros,
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

root_value = Money(42, "DM")

schema = GraphQLSchema(query=queryType, subscription=subscriptionType,)


def test_custom_scalar_in_output():

    client = Client(schema=schema)

    query = gql("{balance}")

    result = client.execute(query, root_value=root_value)

    print(result)

    assert result["balance"] == serialize_money(root_value)


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

    expected_result = {"spend": {"amount": 10, "currency": "DM"}}

    for result in client.subscribe(
        query,
        variable_values=variable_values,
        root_value=root_value,
        serialize_variables=True,
    ):
        print(f"result = {result!r}")
        expected_result["spend"]["amount"] = expected_result["spend"]["amount"] - 1
        assert expected_result == result


async def make_money_backend(aiohttp_server):
    from aiohttp import web

    async def handler(request):
        data = await request.json()
        source = data["query"]

        print(f"data keys = {data.keys()}")
        try:
            variables = data["variables"]
            print(f"variables = {variables!r}")
        except KeyError:
            variables = None

        result = graphql_sync(
            schema, source, variable_values=variables, root_value=root_value
        )

        print(f"backend result = {result!r}")

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

        assert result["balance"] == serialize_money(root_value)


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
@pytest.mark.requests
async def test_custom_scalar_serialize_variables_sync_transport(
    event_loop, aiohttp_server, run_sync_test
):

    server, transport = await make_sync_money_transport(aiohttp_server)

    def test_code():
        with Client(schema=schema, transport=transport,) as session:

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
