import pytest
from graphql import print_ast

from gql import Client
from gql.dsl import DSLMutation, DSLQuery, DSLSchema, DSLSubscription, dsl_gql

from .schema import StarWarsSchema


@pytest.fixture
def ds():
    return DSLSchema(StarWarsSchema)


@pytest.fixture
def client():
    return Client(schema=StarWarsSchema)


def test_invalid_field_on_type_query(ds):
    with pytest.raises(AttributeError) as exc_info:
        ds.Query.extras.select(ds.Character.name)
    assert "Field extras does not exist in type Query." in str(exc_info.value)


def test_incompatible_field(ds):
    with pytest.raises(Exception) as exc_info:
        ds.Query.hero.select("not_a_DSL_FIELD")
    assert "Received incompatible field" in str(exc_info.value)


def test_hero_name_query(ds):
    query = """
hero {
  name
}
    """.strip()
    query_dsl = ds.Query.hero.select(ds.Character.name)
    assert query == str(query_dsl)


def test_hero_name_and_friends_query(ds):
    query = """
hero {
  id
  name
  friends {
    name
  }
}
    """.strip()
    query_dsl = ds.Query.hero.select(
        ds.Character.id,
        ds.Character.name,
        ds.Character.friends.select(ds.Character.name,),
    )
    assert query == str(query_dsl)


def test_hero_id_and_name(ds):
    query = """
hero {
  id
  name
}
    """.strip()
    query_dsl = ds.Query.hero.select(ds.Character.id)
    query_dsl = query_dsl.select(ds.Character.name)
    assert query == str(query_dsl)


def test_nested_query(ds):
    query = """
hero {
  name
  friends {
    name
    appearsIn
    friends {
      name
    }
  }
}
    """.strip()
    query_dsl = ds.Query.hero.select(
        ds.Character.name,
        ds.Character.friends.select(
            ds.Character.name,
            ds.Character.appears_in,
            ds.Character.friends.select(ds.Character.name),
        ),
    )
    assert query == str(query_dsl)


def test_fetch_luke_query(ds):
    query = """
human(id: "1000") {
  name
}
    """.strip()
    query_dsl = ds.Query.human(id="1000").select(ds.Human.name,)

    assert query == str(query_dsl)


def test_fetch_luke_aliased(ds):
    query = """
luke: human(id: "1000") {
  name
}
    """.strip()
    query_dsl = ds.Query.human.args(id=1000).alias("luke").select(ds.Character.name,)
    assert query == str(query_dsl)


def test_fetch_name_aliased(ds: DSLSchema):
    query = """
human(id: "1000") {
  my_name: name
}
    """.strip()
    query_dsl = ds.Query.human.args(id=1000).select(ds.Character.name.alias("my_name"))
    print(str(query_dsl))
    assert query == str(query_dsl)


def test_fetch_name_aliased_as_kwargs(ds: DSLSchema):
    query = """
human(id: "1000") {
  my_name: name
}
    """.strip()
    query_dsl = ds.Query.human.args(id=1000).select(my_name=ds.Character.name,)
    assert query == str(query_dsl)


def test_hero_name_query_result(ds, client):
    query = dsl_gql(DSLQuery(ds.Query.hero.select(ds.Character.name)))
    result = client.execute(query)
    expected = {"hero": {"name": "R2-D2"}}
    assert result == expected


def test_arg_serializer_list(ds, client):
    query = dsl_gql(
        DSLQuery(
            ds.Query.characters.args(ids=[1000, 1001, 1003]).select(ds.Character.name,)
        )
    )
    result = client.execute(query)
    expected = {
        "characters": [
            {"name": "Luke Skywalker"},
            {"name": "Darth Vader"},
            {"name": "Leia Organa"},
        ]
    }
    assert result == expected


def test_arg_serializer_enum(ds, client):
    query = dsl_gql(DSLQuery(ds.Query.hero.args(episode=5).select(ds.Character.name)))
    result = client.execute(query)
    expected = {"hero": {"name": "Luke Skywalker"}}
    assert result == expected


def test_create_review_mutation_result(ds, client):

    query = dsl_gql(
        DSLMutation(
            ds.Mutation.createReview.args(
                episode=6, review={"stars": 5, "commentary": "This is a great movie!"}
            ).select(ds.Review.stars, ds.Review.commentary)
        )
    )
    result = client.execute(query)
    expected = {"createReview": {"stars": 5, "commentary": "This is a great movie!"}}
    assert result == expected


def test_subscription(ds):

    query = dsl_gql(
        DSLSubscription(
            ds.Subscription.reviewAdded(episode=6).select(
                ds.Review.stars, ds.Review.commentary
            )
        )
    )
    assert (
        print_ast(query)
        == """subscription {
  reviewAdded(episode: JEDI) {
    stars
    commentary
  }
}
"""
    )


def test_invalid_arg(ds):
    with pytest.raises(
        KeyError, match="Argument invalid_arg does not exist in Field: Character."
    ):
        ds.Query.hero.args(invalid_arg=5).select(ds.Character.name)


def test_multiple_root_fields(ds, client):
    query = dsl_gql(
        DSLQuery(
            ds.Query.hero.select(ds.Character.name),
            ds.Query.hero(episode=5)
            .alias("hero_of_episode_5")
            .select(ds.Character.name),
        )
    )
    result = client.execute(query)
    expected = {
        "hero": {"name": "R2-D2"},
        "hero_of_episode_5": {"name": "Luke Skywalker"},
    }
    assert result == expected


def test_root_fields_aliased(ds, client):
    query = dsl_gql(
        DSLQuery(
            ds.Query.hero.select(ds.Character.name),
            hero_of_episode_5=ds.Query.hero(episode=5).select(ds.Character.name),
        )
    )
    result = client.execute(query)
    expected = {
        "hero": {"name": "R2-D2"},
        "hero_of_episode_5": {"name": "Luke Skywalker"},
    }
    assert result == expected


def test_operation_name(ds):
    query = dsl_gql(GetHeroName=DSLQuery(ds.Query.hero.select(ds.Character.name),))

    assert (
        print_ast(query)
        == """query GetHeroName {
  hero {
    name
  }
}
"""
    )


def test_multiple_operations(ds):
    query = dsl_gql(
        GetHeroName=DSLQuery(ds.Query.hero.select(ds.Character.name)),
        CreateReviewMutation=DSLMutation(
            ds.Mutation.createReview.args(
                episode=6, review={"stars": 5, "commentary": "This is a great movie!"}
            ).select(ds.Review.stars, ds.Review.commentary)
        ),
    )

    assert (
        print_ast(query)
        == """query GetHeroName {
  hero {
    name
  }
}

mutation CreateReviewMutation {
  createReview(episode: JEDI, review: {stars: 5, \
commentary: "This is a great movie!"}) {
    stars
    commentary
  }
}
"""
    )


def test_dsl_query_all_fields_should_be_instances_of_DSLField():
    with pytest.raises(
        TypeError, match="fields must be instances of DSLField. Received type:"
    ):
        DSLQuery("I am a string")


def test_dsl_query_all_fields_should_correspond_to_the_root_type(ds):
    with pytest.raises(AssertionError) as excinfo:
        DSLQuery(ds.Character.name)

    assert ("Invalid root field for operation QUERY.\n" "Received: Character") in str(
        excinfo.value
    )


def test_dsl_gql_all_arguments_should_be_operations():
    with pytest.raises(
        TypeError, match="Operations should be instances of DSLOperation "
    ):
        dsl_gql("I am a string")


def test_DSLSchema_requires_a_schema(client):
    with pytest.raises(TypeError, match="DSLSchema needs a schema as parameter"):
        DSLSchema(client)


def test_invalid_type(ds):
    with pytest.raises(
        AttributeError, match="Type 'invalid_type' not found in the schema!"
    ):
        ds.invalid_type
