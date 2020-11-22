import pytest

from gql import Client
from gql.dsl import DSLQuery, DSLSchema, dsl_gql
from tests.nested_input.schema import NestedInputSchema


@pytest.fixture
def ds():
    return DSLSchema(NestedInputSchema)


@pytest.fixture
def client():
    return Client(schema=NestedInputSchema)


def test_nested_input(ds, client):
    query = dsl_gql(DSLQuery(ds.Query.echo.args(nested={"foo": 1})))
    assert client.execute(query) == {"echo": '{"foo": 1}'}


def test_nested_input_2(ds, client):
    query = dsl_gql(
        DSLQuery(ds.Query.echo.args(nested={"foo": 1, "child": {"foo": 2}}))
    )
    assert client.execute(query) == {"echo": '{"foo": 1, "child": {"foo": 2}}'}


def test_nested_input_3(ds, client):
    query = dsl_gql(
        DSLQuery(
            ds.Query.echo.args(
                nested={"foo": 1, "child": {"foo": 2, "child": {"foo": 3}}}
            )
        )
    )
    assert client.execute(query) == {
        "echo": '{"foo": 1, "child": {"foo": 2, "child": {"foo": 3}}}'
    }
