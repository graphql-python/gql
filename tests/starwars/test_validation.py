import pytest

from gql import Client, gql

from .schema import StarWarsIntrospection, StarWarsSchema


@pytest.fixture
def local_schema():
    return Client(schema=StarWarsSchema)


@pytest.fixture
def typedef_schema():
    return Client(
        schema="""
schema {
  query: Query
}

interface Character {
  appearsIn: [Episode]
  friends: [Character]
  id: String!
  name: String
}

type Droid implements Character {
  appearsIn: [Episode]
  friends: [Character]
  id: String!
  name: String
  primaryFunction: String
}

enum Episode {
  EMPIRE
  JEDI
  NEWHOPE
}

type Human implements Character {
  appearsIn: [Episode]
  friends: [Character]
  homePlanet: String
  id: String!
  name: String
}

type Query {
  droid(id: String!): Droid
  hero(episode: Episode): Character
  human(id: String!): Human
}"""
    )


@pytest.fixture
def introspection_schema():
    return Client(introspection=StarWarsIntrospection)


@pytest.fixture
def introspection_schema_empty_directives():
    introspection = StarWarsIntrospection

    # Simulate an empty dictionary for directives
    introspection["__schema"]["directives"] = []

    return Client(introspection=introspection)


@pytest.fixture
def introspection_schema_no_directives():
    introspection = StarWarsIntrospection

    # Simulate no directives key
    del introspection["__schema"]["directives"]

    return Client(introspection=introspection)


@pytest.fixture(
    params=[
        "local_schema",
        "typedef_schema",
        "introspection_schema",
        "introspection_schema_empty_directives",
        "introspection_schema_no_directives",
    ]
)
def client(request):
    return request.getfixturevalue(request.param)


def validation_errors(client, query):
    query = gql(query)
    try:
        client.validate(query)
        return False
    except Exception:
        return True


def test_incompatible_request_gql(client):
    with pytest.raises(TypeError):
        gql(123)

    """
    The error generated depends on graphql-core version
    < 3.1.5: "body must be a string"
    >= 3.1.5: some variation of "object of type 'int' has no len()"
              depending on the python environment

    So we are not going to check the exact error message here anymore.
    """

    """
    assert ("body must be a string" in str(exc_info.value)) or (
        "object of type 'int' has no len()" in str(exc_info.value)
    )
    """


def test_nested_query_with_fragment(client):
    query = """
        query NestedQueryWithFragment {
          hero {
            ...NameAndAppearances
            friends {
              ...NameAndAppearances
              friends {
                ...NameAndAppearances
              }
            }
          }
        }
        fragment NameAndAppearances on Character {
          name
          appearsIn
        }
    """
    assert not validation_errors(client, query)


def test_non_existent_fields(client):
    query = """
        query HeroSpaceshipQuery {
          hero {
            favoriteSpaceship
          }
        }
    """
    assert validation_errors(client, query)


def test_require_fields_on_object(client):
    query = """
        query HeroNoFieldsQuery {
          hero
        }
    """
    assert validation_errors(client, query)


def test_disallows_fields_on_scalars(client):
    query = """
        query HeroFieldsOnScalarQuery {
          hero {
            name {
              firstCharacterOfName
            }
          }
        }
    """
    assert validation_errors(client, query)


def test_disallows_object_fields_on_interfaces(client):
    query = """
        query DroidFieldOnCharacter {
          hero {
            name
            primaryFunction
          }
        }
    """
    assert validation_errors(client, query)


def test_allows_object_fields_in_fragments(client):
    query = """
        query DroidFieldInFragment {
          hero {
            name
            ...DroidFields
          }
        }
        fragment DroidFields on Droid {
          primaryFunction
        }
    """
    assert not validation_errors(client, query)


def test_allows_object_fields_in_inline_fragments(client):
    query = """
        query DroidFieldInFragment {
          hero {
            name
            ... on Droid {
              primaryFunction
            }
          }
        }
    """
    assert not validation_errors(client, query)


def test_include_directive(client):
    query = """
        query fetchHero($with_friends: Boolean!) {
          hero {
            name
            friends @include(if: $with_friends) {
                name
            }
          }
        }
    """
    assert not validation_errors(client, query)


def test_skip_directive(client):
    query = """
        query fetchHero($without_friends: Boolean!) {
          hero {
            name
            friends @skip(if: $without_friends) {
                name
            }
          }
        }
    """
    assert not validation_errors(client, query)


def test_build_client_schema_invalid_introspection():
    from gql.utilities import build_client_schema

    with pytest.raises(TypeError) as exc_info:
        build_client_schema("blah")

    assert (
        "Invalid or incomplete introspection result. Ensure that you are passing the "
        "'data' attribute of an introspection response and no 'errors' were returned "
        "alongside: 'blah'."
    ) in str(exc_info.value)
