import pytest
from graphql import (
    FloatValueNode,
    GraphQLError,
    GraphQLFloat,
    GraphQLID,
    GraphQLInputObjectType,
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
)
from graphql import __version__ as graphql_version
from graphql import (
    build_ast_schema,
    parse,
    print_ast,
)
from graphql.utilities import get_introspection_query
from packaging import version

from gql import Client, gql
from gql.dsl import (
    DSLDirective,
    DSLField,
    DSLFragment,
    DSLFragmentSpread,
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
from gql.utilities import get_introspection_query_ast, node_tree

from ..conftest import strip_braces_spaces
from .schema import StarWarsSchema


@pytest.fixture
def ds():
    return DSLSchema(StarWarsSchema)


@pytest.fixture
def var():
    """Common DSLVariableDefinitions fixture for directive tests"""
    return DSLVariableDefinitions()


@pytest.fixture
def client():
    return Client(schema=StarWarsSchema)


def test_ast_from_value_with_input_type_and_not_mapping_value():
    obj_type = StarWarsSchema.get_type("ReviewInput")
    assert isinstance(obj_type, GraphQLInputObjectType)
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
        ast_from_value(4, None)  # type: ignore

    assert "Unexpected input type: None." in str(exc_info.value)


def test_ast_from_value_with_non_null_type_and_none():
    typ = GraphQLNonNull(GraphQLInt)

    with pytest.raises(GraphQLError) as exc_info:
        ast_from_value(None, typ)

    assert "Received Null value for a Non-Null type Int." in str(exc_info.value)


def test_ast_from_value_float_precision():

    # Checking precision of float serialization
    # See https://github.com/graphql-python/graphql-core/pull/164

    assert ast_from_value(123456789.01234567, GraphQLFloat) == FloatValueNode(
        value="123456789.01234567"
    )

    assert ast_from_value(1.1, GraphQLFloat) == FloatValueNode(value="1.1")

    assert ast_from_value(123.0, GraphQLFloat) == FloatValueNode(value="123")


def test_ast_from_serialized_value_untyped_typeerror():
    with pytest.raises(TypeError) as exc_info:
        ast_from_serialized_value_untyped(GraphQLInt)

    assert "Cannot convert value to AST: Int." in str(exc_info.value)


def test_variable_to_ast_type_passing_wrapping_type():
    review_type = StarWarsSchema.get_type("ReviewInput")
    assert isinstance(review_type, GraphQLInputObjectType)

    wrapping_type = GraphQLNonNull(GraphQLList(review_type))
    variable = DSLVariable("review_input")
    ast = variable.to_ast_type(wrapping_type)
    assert ast == NonNullTypeNode(
        type=ListTypeNode(type=NamedTypeNode(name=NameNode(value="ReviewInput")))
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
        print_ast(query.document)
        == """mutation \
($badReview: ReviewInput, $episode: Episode, $goodReview: ReviewInput) {
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

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
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
        print_ast(query.document)
        == """mutation ($review: ReviewInput, $episode: Episode) {
  createReview(review: $review, episode: $episode) {
    stars
    commentary
  }
}"""
    )

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


def test_add_variable_definitions_with_default_value_enum(ds):
    var = DSLVariableDefinitions()
    op = DSLMutation(
        ds.Mutation.createReview.args(
            review=var.review, episode=var.episode.default(4)
        ).select(ds.Review.stars, ds.Review.commentary)
    )
    op.variable_definitions = var
    query = dsl_gql(op)

    assert (
        print_ast(query.document)
        == """mutation ($review: ReviewInput, $episode: Episode = NEWHOPE) {
  createReview(review: $review, episode: $episode) {
    stars
    commentary
  }
}"""
    )


def test_add_variable_definitions_with_default_value_input_object(ds):
    var = DSLVariableDefinitions()
    op = DSLMutation(
        ds.Mutation.createReview.args(
            review=var.review.default({"stars": 5, "commentary": "Wow!"}),
            episode=var.episode,
        ).select(ds.Review.stars, ds.Review.commentary)
    )
    op.variable_definitions = var
    query = dsl_gql(op)

    assert (
        strip_braces_spaces(print_ast(query.document))
        == """
mutation ($review: ReviewInput = {stars: 5, commentary: "Wow!"}, $episode: Episode) {
  createReview(review: $review, episode: $episode) {
    stars
    commentary
  }
}""".strip()
    )

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
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
        strip_braces_spaces(print_ast(query.document))
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

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
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
        ds.Character.friends.select(
            ds.Character.name,
        ),
    )
    assert query == str(query_dsl)

    # Should also work with a chain of selects
    query_dsl = (
        ds.Query.hero.select(ds.Character.id)
        .select(ds.Character.name)
        .select(
            ds.Character.friends.select(
                ds.Character.name,
            ),
        )
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
    query_dsl = ds.Query.human(id="1000").select(
        ds.Human.name,
    )

    assert query == str(query_dsl)


def test_fetch_luke_aliased(ds):
    query = """
luke: human(id: "1000") {
  name
}
    """.strip()
    query_dsl = (
        ds.Query.human.args(id=1000)
        .alias("luke")
        .select(
            ds.Character.name,
        )
    )
    assert query == str(query_dsl)

    # Should also work with select before alias
    query_dsl = (
        ds.Query.human.args(id=1000)
        .select(
            ds.Character.name,
        )
        .alias("luke")
    )
    assert query == str(query_dsl)


def test_fetch_name_aliased(ds: DSLSchema) -> None:
    query = """
human(id: "1000") {
  my_name: name
}
    """.strip()
    query_dsl = ds.Query.human.args(id=1000).select(ds.Character.name.alias("my_name"))
    print(str(query_dsl))
    assert query == str(query_dsl)


def test_fetch_name_aliased_as_kwargs(ds: DSLSchema) -> None:
    query = """
human(id: "1000") {
  my_name: name
}
    """.strip()
    query_dsl = ds.Query.human.args(id=1000).select(
        my_name=ds.Character.name,
    )
    assert query == str(query_dsl)


def test_hero_name_query_result(ds, client):
    query = dsl_gql(DSLQuery(ds.Query.hero.select(ds.Character.name)))
    result = client.execute(query)
    expected = {"hero": {"name": "R2-D2"}}
    assert result == expected
    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


def test_arg_serializer_list(ds, client):
    query = dsl_gql(
        DSLQuery(
            ds.Query.characters.args(ids=[1000, 1001, 1003]).select(
                ds.Character.name,
            )
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
    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


def test_arg_serializer_enum(ds, client):
    query = dsl_gql(DSLQuery(ds.Query.hero.args(episode=5).select(ds.Character.name)))
    result = client.execute(query)
    expected = {"hero": {"name": "Luke Skywalker"}}
    assert result == expected
    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


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
    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


def test_subscription(ds):

    query = dsl_gql(
        DSLSubscription(
            ds.Subscription.reviewAdded(episode=6).select(
                ds.Review.stars, ds.Review.commentary
            )
        )
    )
    assert (
        print_ast(query.document)
        == """subscription {
  reviewAdded(episode: JEDI) {
    stars
    commentary
  }
}"""
    )

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
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
    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


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
    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


def test_operation_name(ds):
    query = dsl_gql(
        GetHeroName=DSLQuery(
            ds.Query.hero.select(ds.Character.name),
        )
    )

    assert (
        print_ast(query.document)
        == """query GetHeroName {
  hero {
    name
  }
}"""
    )

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
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
        strip_braces_spaces(print_ast(query.document))
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

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
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
    assert repr(DSLFragment("fragment_1").spread()) == "<DSLFragmentSpread fragment_1>"
    assert repr(DSLFragment("fragment_2").on(ds.Droid)) == "<DSLFragment fragment_2>"
    assert (
        repr(DSLFragment("fragment_2").on(ds.Droid).spread())
        == "<DSLFragmentSpread fragment_2>"
    )


def test_fragment_spread_instances(ds):
    """Test that each .spread() creates new DSLFragmentSpread instance"""
    fragment = DSLFragment("Test").on(ds.Character).select(ds.Character.name)
    spread1 = fragment.spread()
    spread2 = fragment.spread()

    assert isinstance(spread1, DSLFragmentSpread)
    assert isinstance(spread2, DSLFragmentSpread)
    assert spread1 is not spread2


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

    request = dsl_gql(name_and_appearances, query_dsl)

    document = request.document

    print(print_ast(document))

    assert query == print_ast(document)
    assert node_tree(document) == node_tree(gql(print_ast(document)).document)


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
        GraphQLError,
        match=r"Invalid field for <DSLQuery>: <DSLInlineFragment>",
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

    request = dsl_gql(name_and_appearances, NestedQueryWithFragment=query_dsl)

    document = request.document

    print(print_ast(document))

    assert query == print_ast(document)
    assert node_tree(document) == node_tree(gql(print_ast(document)).document)

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

    request = dsl_gql(name_and_appearances, NestedQueryWithFragment=query_dsl)

    document = request.document

    print(print_ast(document))

    assert query == print_ast(document)
    assert node_tree(document) == node_tree(gql(print_ast(document)).document)


def test_dsl_query_all_fields_should_be_instances_of_DSLField():
    with pytest.raises(
        TypeError,
        match="Fields should be instances of DSLSelectable. Received: <class 'str'>",
    ):
        DSLQuery("I am a string")  # type: ignore


def test_dsl_query_all_fields_should_correspond_to_the_root_type(ds):
    with pytest.raises(GraphQLError) as excinfo:
        DSLQuery(ds.Character.name)

    assert ("Invalid field for <DSLQuery>: <DSLField Character::name>") in str(
        excinfo.value
    )


def test_dsl_root_type_not_default():

    schema_str = """
schema {
  query: QueryNotDefault
}

type QueryNotDefault {
  version: String
}
"""

    type_def_ast = parse(schema_str)
    schema = build_ast_schema(type_def_ast)

    ds = DSLSchema(schema)

    query = dsl_gql(DSLQuery(ds.QueryNotDefault.version))

    expected_query = """
{
  version
}
"""
    assert print_ast(query.document) == expected_query.strip()

    with pytest.raises(GraphQLError) as excinfo:
        DSLSubscription(ds.QueryNotDefault.version)

    assert (
        "Invalid field for <DSLSubscription>: <DSLField QueryNotDefault::version>"
    ) in str(excinfo.value)

    assert node_tree(query.document) == node_tree(
        gql(print_ast(query.document)).document
    )


def test_dsl_gql_all_arguments_should_be_operations_or_fragments():
    with pytest.raises(
        TypeError, match="Operations should be instances of DSLExecutable "
    ):
        dsl_gql("I am a string")  # type: ignore


def test_DSLSchema_requires_a_schema(client):
    with pytest.raises(TypeError, match="DSLSchema needs a schema as parameter"):
        DSLSchema(client)


def test_invalid_type(ds):
    with pytest.raises(
        AttributeError, match="Type 'invalid_type' not found in the schema!"
    ):
        ds.invalid_type


def test_invalid_type_union():
    schema_str = """
    type FloatValue {
        floatValue: Float!
    }

    type IntValue {
        intValue: Int!
    }

    union Value = FloatValue | IntValue

    type Entry {
        name: String!
        value: Value
    }

    type Query {
        values: [Entry!]!
    }
    """

    schema = build_ast_schema(parse(schema_str))
    ds = DSLSchema(schema)

    with pytest.raises(
        AttributeError,
        match=(
            "Type \"Value \\(<GraphQLUnionType 'Value'>\\)\" is not valid as an "
            "attribute of DSLSchema. Only Object types or Interface types are accepted."
        ),
    ):
        ds.Value


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

    assert query == str(print_ast(dsl_gql(query_dsl).document)).strip()


def test_invalid_meta_field_selection(ds):

    DSLQuery(DSLMetaField("__typename"))
    DSLQuery(DSLMetaField("__schema"))
    DSLQuery(DSLMetaField("__type"))

    metafield = DSLMetaField("__typename")
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
        input_value_deprecation=option,
    )
    dsl_introspection_query = get_introspection_query_ast(
        descriptions=option,
        specified_by_url=option,
        directive_is_repeatable=option,
        schema_description=option,
        input_value_deprecation=option,
    )

    try:
        assert print_ast(gql(introspection_query).document) == print_ast(
            dsl_introspection_query
        )
        assert node_tree(dsl_introspection_query) == node_tree(
            gql(print_ast(dsl_introspection_query)).document
        )
    except AssertionError:

        # From graphql-core version 3.3.0a7, there is two more type recursion levels
        dsl_introspection_query = get_introspection_query_ast(
            descriptions=option,
            specified_by_url=option,
            directive_is_repeatable=option,
            schema_description=option,
            input_value_deprecation=option,
            type_recursion_level=9,
        )
        assert print_ast(gql(introspection_query).document) == print_ast(
            dsl_introspection_query
        )
        assert node_tree(dsl_introspection_query) == node_tree(
            gql(print_ast(dsl_introspection_query)).document
        )


@pytest.mark.skipif(
    version.parse(graphql_version) < version.parse("3.3.0a7"),
    reason="Requires graphql-core >= 3.3.0a7",
)
@pytest.mark.parametrize("option", [True, False])
def test_get_introspection_query_ast_is_one_of(option):

    introspection_query = print_ast(
        gql(
            get_introspection_query(
                input_value_deprecation=option,
            )
        ).document
    )

    # Because the option does not exist yet in graphql-core,
    # we add it manually here for now
    if option:
        introspection_query = introspection_query.replace(
            "fields",
            "isOneOf\n  fields",
        )

    dsl_introspection_query = get_introspection_query_ast(
        input_value_deprecation=option,
        input_object_one_of=option,
        type_recursion_level=9,
    )

    assert introspection_query == print_ast(dsl_introspection_query)


@pytest.mark.skipif(
    version.parse(graphql_version) >= version.parse("3.3.0a7"),
    reason="Test only for older graphql-core versions < 3.3.0a7",
)
def test_get_introspection_query_ast_is_one_of_not_implemented_yet():

    with pytest.raises(NotImplementedError):
        get_introspection_query_ast(
            input_object_one_of=True,
        )


def test_typename_aliased(ds):
    query = """
hero {
  name
  typenameField: __typename
}
""".strip()

    query_dsl = ds.Query.hero.select(
        ds.Character.name, typenameField=DSLMetaField("__typename")
    )
    assert query == str(query_dsl)

    query_dsl = ds.Query.hero.select(
        ds.Character.name, DSLMetaField("__typename").alias("typenameField")
    )
    assert query == str(query_dsl)


def test_node_tree_with_loc(ds):
    query = """query GetHeroName {
  hero {
    name
  }
}""".strip()

    document = gql(query).document

    node_tree_result = """
DocumentNode
  definitions:
    OperationDefinitionNode
      directives:
        empty tuple
      loc:
        Location
          <Location 0:43>
      name:
        NameNode
          loc:
            Location
              <Location 6:17>
          value:
            'GetHeroName'
      operation:
        <OperationType.QUERY: 'query'>
      selection_set:
        SelectionSetNode
          loc:
            Location
              <Location 18:43>
          selections:
            FieldNode
              alias:
                None
              arguments:
                empty tuple
              directives:
                empty tuple
              loc:
                Location
                  <Location 22:41>
              name:
                NameNode
                  loc:
                    Location
                      <Location 22:26>
                  value:
                    'hero'
              nullability_assertion:
                None
              selection_set:
                SelectionSetNode
                  loc:
                    Location
                      <Location 27:41>
                  selections:
                    FieldNode
                      alias:
                        None
                      arguments:
                        empty tuple
                      directives:
                        empty tuple
                      loc:
                        Location
                          <Location 33:37>
                      name:
                        NameNode
                          loc:
                            Location
                              <Location 33:37>
                          value:
                            'name'
                      nullability_assertion:
                        None
                      selection_set:
                        None
      variable_definitions:
        empty tuple
  loc:
    Location
      <Location 0:43>
""".strip()

    node_tree_result_stable = """
DocumentNode
  definitions:
    OperationDefinitionNode
      directives:
        empty tuple
      loc:
        Location
          <Location 0:43>
      name:
        NameNode
          loc:
            Location
              <Location 6:17>
          value:
            'GetHeroName'
      operation:
        <OperationType.QUERY: 'query'>
      selection_set:
        SelectionSetNode
          loc:
            Location
              <Location 18:43>
          selections:
            FieldNode
              alias:
                None
              arguments:
                empty tuple
              directives:
                empty tuple
              loc:
                Location
                  <Location 22:41>
              name:
                NameNode
                  loc:
                    Location
                      <Location 22:26>
                  value:
                    'hero'
              selection_set:
                SelectionSetNode
                  loc:
                    Location
                      <Location 27:41>
                  selections:
                    FieldNode
                      alias:
                        None
                      arguments:
                        empty tuple
                      directives:
                        empty tuple
                      loc:
                        Location
                          <Location 33:37>
                      name:
                        NameNode
                          loc:
                            Location
                              <Location 33:37>
                          value:
                            'name'
                      selection_set:
                        None
      variable_definitions:
        empty tuple
  loc:
    Location
      <Location 0:43>
""".strip()

    print(node_tree(document, ignore_loc=False))

    try:
        assert node_tree(document, ignore_loc=False) == node_tree_result
    except AssertionError:
        # graphql-core version 3.2.3
        assert node_tree(document, ignore_loc=False) == node_tree_result_stable


def test_legacy_fragment_with_variables(ds):
    var = DSLVariableDefinitions()

    hero_fragment = (
        DSLFragment("heroFragment")
        .on(ds.Query)
        .select(
            ds.Query.hero.args(episode=var.episode).select(ds.Character.name),
        )
    )

    print(hero_fragment)

    hero_fragment.variable_definitions = var

    query = dsl_gql(hero_fragment)

    expected = """
fragment heroFragment($episode: Episode) on Query {
  hero(episode: $episode) {
    name
  }
}
""".strip()
    assert print_ast(query.document) == expected


@pytest.mark.parametrize(
    "shortcut,expected",
    [
        ("__typename", DSLMetaField("__typename")),
        ("__schema", DSLMetaField("__schema")),
        ("__type", DSLMetaField("__type")),
        ("...", DSLInlineFragment()),
        ("@skip", DSLDirective(name="skip", dsl_schema=DSLSchema(StarWarsSchema))),
    ],
)
def test_dsl_schema_call_shortcuts(ds, shortcut, expected):
    actual = ds(shortcut)
    assert getattr(actual, "name", None) == getattr(expected, "name", None)
    assert isinstance(actual, type(expected))


def test_dsl_schema_call_validation(ds):
    with pytest.raises(ValueError, match="(?i)unsupported shortcut"):
        ds("foo")


def test_executable_directives(ds, var):
    """Test ALL executable directive locations and types in one document"""

    # Fragment with both built-in and custom directives
    fragment = (
        DSLFragment("CharacterInfo")
        .on(ds.Character)
        .select(ds.Character.name, ds.Character.appearsIn)
        .directives(ds("@fragmentDefinition"))
    )

    # Query with multiple directive types
    query = DSLQuery(
        ds.Query.hero.args(episode=var.episode).select(
            # Field with both built-in and custom directives
            ds.Character.name.directives(
                ds("@skip")(**{"if": var.skipName}),
                ds("@field"),  # custom field directive
            ),
            # Field with repeated directives (same directive multiple times)
            ds.Character.appearsIn.directives(
                ds("@repeat")(value="first"),
                ds("@repeat")(value="second"),
                ds("@repeat")(value="third"),
            ),
            # Fragment spread with multiple directives
            fragment.spread().directives(
                ds("@include")(**{"if": var.includeSpread}),
                ds("@fragmentSpread"),
            ),
            # Inline fragment with directives
            DSLInlineFragment()
            .on(ds.Human)
            .select(ds.Human.homePlanet)
            .directives(
                ds("@skip")(**{"if": var.skipInline}),
                ds("@inlineFragment"),
            ),
            # Meta field with directive
            DSLMetaField("__typename").directives(
                ds("@include")(**{"if": var.includeType})
            ),
        )
    ).directives(ds("@query"))

    # Mutation with directives
    mutation = DSLMutation(
        ds.Mutation.createReview.args(
            episode=6, review={"stars": 5, "commentary": "Great!"}
        ).select(ds.Review.stars, ds.Review.commentary)
    ).directives(ds("@mutation"))

    # Subscription with directives
    subscription = DSLSubscription(
        ds.Subscription.reviewAdded.args(episode=6).select(
            ds.Review.stars, ds.Review.commentary
        )
    ).directives(ds("@subscription"))

    # Variable definitions with directives
    var.episode.directives(
        # Note that `$episode: Episode @someDirective(value=$someValue)`
        # is INVALID GraphQL because variable definitions must be literal values
        ds("@variableDefinition"),
    )
    query.variable_definitions = var

    # Generate ONE document with everything
    doc = dsl_gql(
        fragment, HeroQuery=query, CreateReview=mutation, ReviewSub=subscription
    )

    expected = """\
fragment CharacterInfo on Character @fragmentDefinition {
  name
  appearsIn
}

query HeroQuery(\
$episode: Episode @variableDefinition, \
$skipName: Boolean!, \
$includeSpread: Boolean!, \
$skipInline: Boolean!, \
$includeType: Boolean!\
) @query {
  hero(episode: $episode) {
    name @skip(if: $skipName) @field
    appearsIn @repeat(value: "first") @repeat(value: "second") @repeat(value: "third")
    ...CharacterInfo @include(if: $includeSpread) @fragmentSpread
    ... on Human @skip(if: $skipInline) @inlineFragment {
      homePlanet
    }
    __typename @include(if: $includeType)
  }
}

mutation CreateReview @mutation {
  createReview(episode: JEDI, review: {stars: 5, commentary: "Great!"}) {
    stars
    commentary
  }
}

subscription ReviewSub @subscription {
  reviewAdded(episode: JEDI) {
    stars
    commentary
  }
}"""

    assert strip_braces_spaces(print_ast(doc.document)) == expected
    assert node_tree(doc.document) == node_tree(gql(expected).document)


def test_directive_repr(ds):
    """Test DSLDirective string representation"""
    directive = ds("@include")(**{"if": True})
    expected = "<DSLDirective @include(if=True)>"
    assert repr(directive) == expected


def test_directive_error_handling(ds):
    """Test error handling for directives"""
    # Invalid directive argument type
    with pytest.raises(TypeError, match="Expected DSLDirective"):
        ds.Query.hero.directives(123)

    # Invalid directive name from `__call__
    with pytest.raises(GraphQLError, match="Directive '@nonexistent' not found"):
        ds("@nonexistent")

    # Invalid directive argument
    with pytest.raises(GraphQLError, match="Argument 'invalid' does not exist"):
        ds("@include")(invalid=True)

    # Tried to set arguments twice
    with pytest.raises(
        AttributeError, match="Arguments for directive @field already set."
    ):
        ds("@field").args(value="foo").args(value="bar")

    with pytest.raises(
        GraphQLError,
        match="(?i)Directive '@deprecated' is not a valid request executable directive",
    ):
        ds("@deprecated")

    with pytest.raises(GraphQLError, match="unexpected variable"):
        # variable definitions must be static, literal values defined in the query!
        var = DSLVariableDefinitions()
        query = DSLQuery(
            ds.Query.hero.args(episode=var.episode).select(ds.Character.name)
        )
        var.episode.directives(
            ds("@variableDefinition").args(value=var.nonStatic),
        )
        query.variable_definitions = var
        _ = dsl_gql(query).document


# Parametrized tests for comprehensive directive location validation
@pytest.fixture(
    params=[
        "@query",
        "@mutation",
        "@subscription",
        "@field",
        "@fragmentDefinition",
        "@fragmentSpread",
        "@inlineFragment",
        "@variableDefinition",
    ]
)
def directive_name(request):
    return request.param


@pytest.fixture(
    params=[
        (DSLQuery, "QUERY"),
        (DSLMutation, "MUTATION"),
        (DSLSubscription, "SUBSCRIPTION"),
        (DSLField, "FIELD"),
        (DSLMetaField, "FIELD"),
        (DSLFragment, "FRAGMENT_DEFINITION"),
        (DSLFragmentSpread, "FRAGMENT_SPREAD"),
        (DSLInlineFragment, "INLINE_FRAGMENT"),
        (DSLVariable, "VARIABLE_DEFINITION"),
    ]
)
def dsl_class_and_location(request):
    return request.param


@pytest.fixture
def is_valid_combination(directive_name, dsl_class_and_location):
    # Map directive names to their expected locations
    directive_to_location = {
        "@query": "QUERY",
        "@mutation": "MUTATION",
        "@subscription": "SUBSCRIPTION",
        "@field": "FIELD",
        "@fragmentDefinition": "FRAGMENT_DEFINITION",
        "@fragmentSpread": "FRAGMENT_SPREAD",
        "@inlineFragment": "INLINE_FRAGMENT",
        "@variableDefinition": "VARIABLE_DEFINITION",
    }
    expected_location = directive_to_location[directive_name]
    _, actual_location = dsl_class_and_location
    return expected_location == actual_location


def create_dsl_instance(dsl_class, ds):
    """Helper function to create DSL instances for testing"""
    if dsl_class == DSLQuery:
        return DSLQuery(ds.Query.hero.select(ds.Character.name))
    elif dsl_class == DSLMutation:
        return DSLMutation(
            ds.Mutation.createReview.args(episode=6, review={"stars": 5}).select(
                ds.Review.stars
            )
        )
    elif dsl_class == DSLSubscription:
        return DSLSubscription(
            ds.Subscription.reviewAdded.args(episode=6).select(ds.Review.stars)
        )
    elif dsl_class == DSLField:
        return ds.Query.hero
    elif dsl_class == DSLMetaField:
        return DSLMetaField("__typename")
    elif dsl_class == DSLFragment:
        return DSLFragment("test").on(ds.Character).select(ds.Character.name)
    elif dsl_class == DSLFragmentSpread:
        fragment = DSLFragment("test").on(ds.Character).select(ds.Character.name)
        return fragment.spread()
    elif dsl_class == DSLInlineFragment:
        return DSLInlineFragment().on(ds.Human).select(ds.Human.homePlanet)
    elif dsl_class == DSLVariable:
        var = DSLVariableDefinitions()
        return var.testVar
    else:
        raise ValueError(f"Unknown DSL class: {dsl_class}")


def test_directive_location_validation(
    ds, directive_name, dsl_class_and_location, is_valid_combination
):
    """Test all 64 combinations of 8 directives × 8 DSL classes"""
    dsl_class, _ = dsl_class_and_location
    directive = ds(directive_name)

    # Create instance of DSL class and try to apply directive
    instance = create_dsl_instance(dsl_class, ds)

    if is_valid_combination:
        # Should work without error
        instance.directives(directive)
    else:
        # Should raise GraphQLError for invalid location
        with pytest.raises(GraphQLError, match="Invalid directive location"):
            instance.directives(directive)
