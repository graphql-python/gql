from gql import gql


gql('''
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
''')

gql('''
    query HeroSpaceshipQuery {
      hero {
        favoriteSpaceship
      }
    }
''') # GQL101

gql('''
    query HeroNoFieldsQuery {
      hero
    }
''') # GQL101


gql('''
    query HeroFieldsOnScalarQuery {
      hero {
        name {
          firstCharacterOfName
        }
      }
    }
''') # GQL101


gql('''
    query DroidFieldOnCharacter {
      hero {
        name
        primaryFunction
      }
    }
''') # GQL101

gql('''
    query DroidFieldInFragment {
      hero {
        name
        ...DroidFields
      }
    }
    fragment DroidFields on Droid {
      primaryFunction
    }
''')

gql('''
    query DroidFieldInFragment {
      hero {
        name
        ... on Droid {
          primaryFunction
        }
      }
    }
''')
