import pytest

from gql import Client
from gql.dsl import DSLSchema, dsl_gql
from tests.nested_input.schema import NestedInputSchema


@pytest.fixture
def ds():
    return DSLSchema(NestedInputSchema)


@pytest.fixture
def client():
    return Client(schema=NestedInputSchema)


def test_nested_input_with_new_get_arg_serializer(ds, client):
    query = dsl_gql(ds.Query.foo.args(nested={"foo": 1}))
    assert client.execute(query) == {"foo": 1}
