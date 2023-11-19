from gql import Client, gql
from gql.dsl import DSLFragment, DSLQuery, DSLSchema, dsl_gql, print_ast
from gql.utilities import node_tree

schema_str = """
type MonsterForm {
  sprites: MonsterFormSprites!
}

union SpriteUnion = Sprite | CopyOf

type Query {
  monster: [Monster!]!
}

type MonsterFormSprites {
  actions: [SpriteUnion!]!
}

type CopyOf {
  action: String!
}

type Monster {
  manual(path: String!): MonsterForm
}

type Sprite {
  action: String!
}
"""


def test_issue_447():

    client = Client(schema=schema_str)
    ds = DSLSchema(client.schema)

    sprite = DSLFragment("SpriteUnionAsSprite")
    sprite.on(ds.Sprite)
    sprite.select(
        ds.Sprite.action,
    )
    copy_of = DSLFragment("SpriteUnionAsCopyOf")
    copy_of.on(ds.CopyOf)
    copy_of.select(
        ds.CopyOf.action,
    )

    query = ds.Query.monster.select(
        ds.Monster.manual(path="").select(
            ds.MonsterForm.sprites.select(
                ds.MonsterFormSprites.actions.select(sprite, copy_of),
            ),
        ),
    )

    q = dsl_gql(sprite, copy_of, DSLQuery(query))

    client.validate(q)

    # Creating a tree from the DocumentNode created by dsl_gql
    dsl_tree = node_tree(q)

    # Creating a tree from the DocumentNode created by gql
    gql_tree = node_tree(gql(print_ast(q)))

    print("=======")
    print(dsl_tree)
    print("+++++++")
    print(gql_tree)
    print("=======")

    assert dsl_tree == gql_tree
