import pytest
from graphql import print_schema

from gql import Client

from .fixtures import make_starwars_transport

# Marking all tests in this file with the aiohttp marker
pytestmark = pytest.mark.aiohttp


@pytest.mark.asyncio
async def test_starwars_introspection_args(event_loop, aiohttp_server):

    transport = await make_starwars_transport(aiohttp_server)

    # First fetch the schema from transport using default introspection query
    # We should receive descriptions in the schema but not deprecated input fields
    async with Client(
        transport=transport,
        fetch_schema_from_transport=True,
    ) as session:

        schema_str = print_schema(session.client.schema)
        print(schema_str)

        assert '"""The number of stars this review gave, 1-5"""' in schema_str
        assert "deprecated_input_field" not in schema_str

    # Then fetch the schema from transport using an introspection query
    # without requesting descriptions
    # We should NOT receive descriptions in the schema
    async with Client(
        transport=transport,
        fetch_schema_from_transport=True,
        introspection_args={
            "descriptions": False,
        },
    ) as session:

        schema_str = print_schema(session.client.schema)
        print(schema_str)

        assert '"""The number of stars this review gave, 1-5"""' not in schema_str
        assert "deprecated_input_field" not in schema_str

    # Then fetch the schema from transport using and introspection query
    # requiring deprecated input fields
    # We should receive descriptions in the schema and deprecated input fields
    async with Client(
        transport=transport,
        fetch_schema_from_transport=True,
        introspection_args={
            "input_value_deprecation": True,
        },
    ) as session:

        schema_str = print_schema(session.client.schema)
        print(schema_str)

        assert '"""The number of stars this review gave, 1-5"""' in schema_str
        assert "deprecated_input_field" in schema_str
