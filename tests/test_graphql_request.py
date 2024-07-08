import asyncio
from math import isfinite
from typing import Any, Dict, NamedTuple, Optional

import pytest
from graphql.error import GraphQLError
from graphql.language import ValueNode
from graphql.pyutils import inspect
from graphql.type import (
    GraphQLArgument,
    GraphQLField,
    GraphQLFloat,
    GraphQLList,
    GraphQLNonNull,
    GraphQLObjectType,
    GraphQLScalarType,
    GraphQLSchema,
)
from graphql.utilities import value_from_ast_untyped

from gql import GraphQLRequest, gql

from .conftest import MS

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
            GraphQLNonNull(countriesBalance),
            resolve=resolve_countries_balance,
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

schema = GraphQLSchema(
    query=queryType,
    subscription=subscriptionType,
)


def test_serialize_variables_using_money_example():
    req = GraphQLRequest(document=gql("{balance}"))

    money_value = Money(10, "DM")

    req = GraphQLRequest(
        document=gql("query myquery($money: Money) {toEuros(money: $money)}"),
        variable_values={"money": money_value},
    )

    req = req.serialize_variable_values(schema)

    assert req.variable_values == {"money": {"amount": 10, "currency": "DM"}}
