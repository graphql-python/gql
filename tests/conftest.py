import pytest

from gql import gql


@pytest.fixture()
def gql_query():
    return gql('''
    {
      myFavoriteFilm: film(id:"RmlsbToz") {
        id
        title
        episodeId
      }
    }
    ''')
