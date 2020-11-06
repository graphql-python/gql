import pytest

from gql import Client
from gql.dsl import DSLSchema
from tests.nested_input.schema import NestedInputSchema


@pytest.fixture
def ds():
    client = Client(schema=NestedInputSchema)
    ds = DSLSchema(client)
    return ds


def test_nested_input_with_new_get_arg_serializer(ds):
    assert ds.query(ds.Query.foo.args(nested={"foo": 1})) == {"foo": 1}
