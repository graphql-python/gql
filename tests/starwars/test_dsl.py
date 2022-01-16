import pytest
from graphql import (
    GraphQLError,
    GraphQLID,
    GraphQLInt,
    GraphQLList,
    GraphQLNonNull,
    IntValueNode,
    ListTypeNode,
    NamedTypeNode,
    NameNode,
    NonNullTypeNode,
    NullValueNode,
    Undefined,
    print_ast,
)
from graphql.utilities import get_introspection_query

from gql import Client, gql
from gql.dsl import (
    DSLFragment,
    DSLInlineFragment,
    DSLMetaField,
    DSLMutation,
    DSLQuery,
    DSLSchema,
    DSLSubscription,
    DSLVariable,
    DSLVariableDefinitions,
    ast_from_serialized_value_untyped,
    ast_from_value,
    dsl_gql,
)
from gql.utilities import get_introspection_query_ast

from .schema import StarWarsSchema


@pytest.fixture
def ds():
    return DSLSchema(StarWarsSchema)


@pytest.fixture
def client():
    return Client(schema=StarWarsSchema)


def test_ast_from_value_with_input_type_and_not_mapping_value():
    obj_type = StarWarsSchema.get_type("ReviewInput")
    assert ast_from_value(8, obj_type) is None


def test_ast_from_value_with_list_type_and_non_iterable_value():
    assert ast_from_value(5, GraphQLList(GraphQLInt)) == IntValueNode(value="5")


def test_ast_from_value_with_none():
    assert ast_from_value(None, GraphQLInt) == NullValueNode()


def test_ast_from_value_with_undefined():
    with pytest.raises(GraphQLError) as exc_info:
        ast_from_value(Undefined, GraphQLInt)

    assert "Received Undefined value for type Int." in str(exc_info.value)


def test_ast_from_value_with_graphqlid():

    assert ast_from_value("12345", GraphQLID) == IntValueNode(value="12345")


def test_ast_from_value_with_invalid_type():
    with pytest.raises(TypeError) as exc_info:
        ast_from_value(4, None)

    assert "Unexpected input type: None." in str(exc_info.value)


def test_ast_from_value_with_non_null_type_and_none():
    typ = GraphQLNonNull(GraphQLInt)

    with pytest.raises(GraphQLError) as exc_info:
        ast_from_value(None, typ)

    assert "Received Null value for a Non-Null type Int." in str(exc_info.value)


def test_ast_from_serialized_value_untyped_typeerror():
    with pytest.raises(TypeError) as exc_info:
        ast_from_serialized_value_untyped(GraphQLInt)

    assert "Cannot convert value to AST: Int." in str(exc_info.value)


def test_variable_to_ast_type_passing_wrapping_type():
    wrapping_type = GraphQLNonNull(GraphQLList(StarWarsSchema.get_type("Droid")))
    variable = DSLVariable("droids")
    ast = variable.to_ast_type(wrapping_type)
    assert ast == NonNullTypeNode(
        type=ListTypeNode(type=NamedTypeNode(name=NameNode(value="Droid")))
    )


def test_use_variable_definition_multiple_times(ds):
    var = DSLVariableDefinitions()

    # `episode` variable is used in both fields
    op = DSLMutation(
        ds.Mutation.createReview.alias("badReview")
        .args(review=var.badReview, episode=var.episode)
        .select(ds.Review.stars, ds.Review.commentary),
        ds.Mutation.createReview.alias("goodReview")
        .args(review=var.goodReview, episode=var.episode)
        .select(ds.Review.stars, ds.Review.commentary),
    )
    op.variable_definitions = var
    query = dsl_gql(op)

    assert (
        print_ast(query)
        == """mutation ($badReview: ReviewInput, $episode: Episode, $goodReview: ReviewInput) {
  badReview: createReview(review: $badReview, episode: $episode) {
    stars
    commentary
  }
  goodReview: createReview(review: $goodReview, episode: $episode) {
    stars
    commentary
  }
}"""
    )


def test_add_variable_definitions(ds):
    var = DSLVariableDefinitions()
    op = DSLMutation(
        ds.Mutation.createReview.args(review=var.review, episode=var.episode).select(
            ds.Review.stars, ds.Review.commentary
        )
    )
    op.variable_definitions = var
    query = dsl_gql(op)

    assert (
        print_ast(query)
        == """mutation ($review: ReviewInput, $episode: Episode) {
  createReview(review: $review, episode: $episode) {
    stars
    commentary
  }
}"""
    )


def test_add_variable_definitions_in_input_object(ds):
    var = DSLVariableDefinitions()
    op = DSLMutation(
        ds.Mutation.createReview.args(
            review={"stars": var.stars, "commentary": var.commentary},
            episode=var.episode,
        ).select(ds.Review.stars, ds.Review.commentary)
    )
    op.variable_definitions = var
    query = dsl_gql(op)

    assert (
        print_ast(query)
        == """mutation ($stars: Int, $commentary: String, $episode: Episode) {
  createReview(
    review: {stars: $stars, commentary: $commentary}
    episode: $episode
  ) {
    stars
    commentary
  }
}"""
    )


def test_invalid_field_on_type_query(ds):
    with pytest.raises(AttributeError) as exc_info:
        ds.Query.extras.select(ds.Character.name)
    assert "Field extras does not exist in type Query." in str(exc_info.value)


def test_incompatible_field(ds):
    with pytest.raises(TypeError) as exc_info:
        ds.Query.hero.select("not_a_DSL_FIELD")
    assert (
        "Fields should be instances of DSLSelectable. Received: <class 'str'>"
        in str(exc_info.value)
    )


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

    # Should also work with a chain of selects
    query_dsl = (
        ds.Query.hero.select(ds.Character.id)
        .select(ds.Character.name)
        .select(ds.Character.friends.select(ds.Character.name,),)
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

    # Should also work with select before alias
    query_dsl = ds.Query.human.args(id=1000).select(ds.Character.name,).alias("luke")
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
}"""
    )


def test_field_does_not_exit_in_type(ds):
    with pytest.raises(
        GraphQLError,
        match="Invalid field for <DSLField Query::hero>: <DSLField Query::hero>",
    ):
        ds.Query.hero.select(ds.Query.hero)


def test_try_to_select_on_scalar_field(ds):
    with pytest.raises(
        GraphQLError,
        match="Invalid field for <DSLField Human::name>: <DSLField Query::hero>",
    ):
        ds.Human.name.select(ds.Query.hero)


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
}"""
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
  createReview(
    episode: JEDI
    review: {stars: 5, commentary: "This is a great movie!"}
  ) {
    stars
    commentary
  }
}"""
    )


def test_inline_fragments(ds):
    query = """hero(episode: JEDI) {
  name
  ... on Droid {
    primaryFunction
  }
  ... on Human {
    homePlanet
  }
}"""
    query_dsl = ds.Query.hero.args(episode=6).select(
        ds.Character.name,
        DSLInlineFragment().on(ds.Droid).select(ds.Droid.primaryFunction),
        DSLInlineFragment().on(ds.Human).select(ds.Human.homePlanet),
    )
    assert query == str(query_dsl)


def test_inline_fragments_nested(ds):
    query = """hero(episode: JEDI) {
  name
  ... on Human {
    ... on Human {
      homePlanet
    }
  }
}"""
    query_dsl = ds.Query.hero.args(episode=6).select(
        ds.Character.name,
        DSLInlineFragment()
        .on(ds.Human)
        .select(DSLInlineFragment().on(ds.Human).select(ds.Human.homePlanet)),
    )
    assert query == str(query_dsl)


def test_fragments_repr(ds):

    assert repr(DSLInlineFragment()) == "<DSLInlineFragment>"
    assert repr(DSLInlineFragment().on(ds.Droid)) == "<DSLInlineFragment on Droid>"
    assert repr(DSLFragment("fragment_1")) == "<DSLFragment fragment_1>"
    assert repr(DSLFragment("fragment_2").on(ds.Droid)) == "<DSLFragment fragment_2>"


def test_fragments(ds):
    query = """fragment NameAndAppearances on Character {
  name
  appearsIn
}

{
  hero {
    ...NameAndAppearances
  }
}"""

    name_and_appearances = (
        DSLFragment("NameAndAppearances")
        .on(ds.Character)
        .select(ds.Character.name, ds.Character.appearsIn)
    )

    query_dsl = DSLQuery(ds.Query.hero.select(name_and_appearances))

    document = dsl_gql(name_and_appearances, query_dsl)

    print(print_ast(document))

    assert query == print_ast(document)


def test_fragment_without_type_condition_error(ds):

    # We create a fragment without using the .on(type_condition) method
    name_and_appearances = DSLFragment("NameAndAppearances")

    # If we try to use this fragment, gql generates an error
    with pytest.raises(
        AttributeError,
        match=r"Missing type condition. Please use .on\(type_condition\) method",
    ):
        dsl_gql(name_and_appearances)

    with pytest.raises(
        AttributeError,
        match=r"Missing type condition. Please use .on\(type_condition\) method",
    ):
        DSLFragment("NameAndAppearances").select(
            ds.Character.name, ds.Character.appearsIn
        )


def test_inline_fragment_in_dsl_gql(ds):

    inline_fragment = DSLInlineFragment()

    query = DSLQuery()

    with pytest.raises(
        GraphQLError, match=r"Invalid field for <DSLQuery>: <DSLInlineFragment>",
    ):
        query.select(inline_fragment)


def test_fragment_with_name_changed(ds):

    fragment = DSLFragment("ABC")

    assert str(fragment) == "...ABC"

    fragment.name = "DEF"

    assert str(fragment) == "...DEF"


def test_fragment_select_field_not_in_fragment(ds):

    fragment = DSLFragment("test").on(ds.Character)

    with pytest.raises(
        GraphQLError,
        match="Invalid field for <DSLFragment test>: <DSLField Droid::primaryFunction>",
    ):
        fragment.select(ds.Droid.primaryFunction)


def test_dsl_nested_query_with_fragment(ds):
    query = """fragment NameAndAppearances on Character {
  name
  appearsIn
}

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
}"""

    name_and_appearances = (
        DSLFragment("NameAndAppearances")
        .on(ds.Character)
        .select(ds.Character.name, ds.Character.appearsIn)
    )

    query_dsl = DSLQuery(
        ds.Query.hero.select(
            name_and_appearances,
            ds.Character.friends.select(
                name_and_appearances, ds.Character.friends.select(name_and_appearances)
            ),
        )
    )

    document = dsl_gql(name_and_appearances, NestedQueryWithFragment=query_dsl)

    print(print_ast(document))

    assert query == print_ast(document)

    # Same thing, but incrementaly

    name_and_appearances = DSLFragment("NameAndAppearances")
    name_and_appearances.on(ds.Character)
    name_and_appearances.select(ds.Character.name)
    name_and_appearances.select(ds.Character.appearsIn)

    level_2 = ds.Character.friends
    level_2.select(name_and_appearances)
    level_1 = ds.Character.friends
    level_1.select(name_and_appearances)
    level_1.select(level_2)

    hero = ds.Query.hero
    hero.select(name_and_appearances)
    hero.select(level_1)

    query_dsl = DSLQuery(hero)

    document = dsl_gql(name_and_appearances, NestedQueryWithFragment=query_dsl)

    print(print_ast(document))

    assert query == print_ast(document)


def test_dsl_query_all_fields_should_be_instances_of_DSLField():
    with pytest.raises(
        TypeError,
        match="Fields should be instances of DSLSelectable. Received: <class 'str'>",
    ):
        DSLQuery("I am a string")


def test_dsl_query_all_fields_should_correspond_to_the_root_type(ds):
    with pytest.raises(GraphQLError) as excinfo:
        DSLQuery(ds.Character.name)

    assert ("Invalid field for <DSLQuery>: <DSLField Character::name>") in str(
        excinfo.value
    )


def test_dsl_gql_all_arguments_should_be_operations_or_fragments():
    with pytest.raises(
        TypeError, match="Operations should be instances of DSLExecutable "
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


def test_hero_name_query_with_typename(ds):
    query = """
hero {
  name
  __typename
}
    """.strip()
    query_dsl = ds.Query.hero.select(ds.Character.name, DSLMetaField("__typename"))
    assert query == str(query_dsl)


def test_type_hero_query(ds):
    query = """{
  __type(name: "Hero") {
    kind
    name
    ofType {
      kind
      name
    }
  }
}"""

    type_hero = DSLMetaField("__type")(name="Hero")
    type_hero.select(
        ds.__Type.kind,
        ds.__Type.name,
        ds.__Type.ofType.select(ds.__Type.kind, ds.__Type.name),
    )
    query_dsl = DSLQuery(type_hero)

    assert query == str(print_ast(dsl_gql(query_dsl))).strip()


def test_invalid_meta_field_selection(ds):

    DSLQuery(DSLMetaField("__typename"))
    DSLQuery(DSLMetaField("__schema"))
    DSLQuery(DSLMetaField("__type"))

    metafield = DSLMetaField("__typename")
    assert metafield.name == "__typename"

    # alias does not work
    metafield.alias("test")

    assert metafield.name == "__typename"

    with pytest.raises(GraphQLError):
        DSLMetaField("__invalid_meta_field")

    DSLMutation(DSLMetaField("__typename"))

    with pytest.raises(GraphQLError):
        DSLMutation(DSLMetaField("__schema"))

    with pytest.raises(GraphQLError):
        DSLMutation(DSLMetaField("__type"))

    with pytest.raises(GraphQLError):
        DSLSubscription(DSLMetaField("__typename"))

    with pytest.raises(GraphQLError):
        DSLSubscription(DSLMetaField("__schema"))

    with pytest.raises(GraphQLError):
        DSLSubscription(DSLMetaField("__type"))

    fragment = DSLFragment("blah")

    with pytest.raises(AttributeError):
        fragment.select(DSLMetaField("__typename"))

    fragment.on(ds.Character)

    fragment.select(DSLMetaField("__typename"))

    with pytest.raises(GraphQLError):
        fragment.select(DSLMetaField("__schema"))

    with pytest.raises(GraphQLError):
        fragment.select(DSLMetaField("__type"))

    ds.Query.hero.select(DSLMetaField("__typename"))

    with pytest.raises(GraphQLError):
        ds.Query.hero.select(DSLMetaField("__schema"))

    with pytest.raises(GraphQLError):
        ds.Query.hero.select(DSLMetaField("__type"))


@pytest.mark.parametrize("option", [True, False])
def test_get_introspection_query_ast(option):

    introspection_query = get_introspection_query(
        descriptions=option,
        specified_by_url=option,
        directive_is_repeatable=option,
        schema_description=option,
    )
    dsl_introspection_query = get_introspection_query_ast(
        descriptions=option,
        specified_by_url=option,
        directive_is_repeatable=option,
        schema_description=option,
    )

    assert print_ast(gql(introspection_query)) == print_ast(dsl_introspection_query)
