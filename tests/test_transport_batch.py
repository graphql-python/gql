import os

import pytest

from gql import Client, gql

# We serve https://github.com/graphql-python/swapi-graphene locally:
URL = "http://127.0.0.1:8000/graphql"

# Marking all tests in this file with the requests marker
pytestmark = pytest.mark.requests


def use_cassette(name):
    import json

    import vcr

    # method to ignore introspection changes in graphql-core 3.3.0b0
    def graphql_body_matcher(r1, r2):
        try:
            b1 = json.loads(r1.body)
            b2 = json.loads(r2.body)
            if isinstance(b1, dict) and isinstance(b2, dict):
                q1 = b1.get("query", "")
                q2 = b2.get("query", "")
                if "IntrospectionQuery" in q1 and "IntrospectionQuery" in q2:
                    return True
                return b1 == b2
            elif isinstance(b1, list) and isinstance(b2, list) and len(b1) == len(b2):
                for item1, item2 in zip(b1, b2):
                    q1 = item1.get("query", "")
                    q2 = item2.get("query", "")
                    if "IntrospectionQuery" in q1 and "IntrospectionQuery" in q2:
                        continue
                    if item1 != item2:
                        return False
                return True
        except Exception:
            pass
        return r1.body == r2.body

    query_vcr = vcr.VCR(
        cassette_library_dir=os.path.join(
            os.path.dirname(__file__), "fixtures", "vcr_cassettes"
        ),
        record_mode="new_episodes",
    )
    query_vcr.register_matcher("graphql_body", graphql_body_matcher)
    query_vcr.match_on = ["uri", "method", "graphql_body"]

    return query_vcr.use_cassette(name + ".yaml")


@pytest.fixture
def client():
    import requests

    from gql.transport.requests import RequestsHTTPTransport

    with use_cassette("client"):
        response = requests.get(
            URL, headers={"Host": "swapi.graphene-python.org", "Accept": "text/html"}
        )
        response.raise_for_status()
        csrf = response.cookies["csrftoken"]

        return Client(
            transport=RequestsHTTPTransport(
                url=URL, cookies={"csrftoken": csrf}, headers={"x-csrftoken": csrf}
            ),
            fetch_schema_from_transport=True,
            introspection_args={
                "input_value_deprecation": False,
            },
        )


def test_hero_name_query(client):
    query = gql("""
        {
          myFavoriteFilm: film(id:"RmlsbToz") {
            id
            title
            episodeId
            characters(first:5) {
              edges {
                node {
                  name
                }
              }
            }
          }
        }
        """)
    expected = [
        {
            "myFavoriteFilm": {
                "id": "RmlsbToz",
                "title": "Return of the Jedi",
                "episodeId": 6,
                "characters": {
                    "edges": [
                        {"node": {"name": "Luke Skywalker"}},
                        {"node": {"name": "C-3PO"}},
                        {"node": {"name": "R2-D2"}},
                        {"node": {"name": "Darth Vader"}},
                        {"node": {"name": "Leia Organa"}},
                    ]
                },
            }
        }
    ]
    with use_cassette("queries_batch"):
        results = client.execute_batch([query])
    assert results == expected


def test_query_with_variable(client):
    query = gql("""
        query Planet($id: ID!) {
          planet(id: $id) {
            id
            name
          }
        }
        """)
    query.variable_values = {"id": "UGxhbmV0OjEw"}
    expected = [{"planet": {"id": "UGxhbmV0OjEw", "name": "Kamino"}}]
    with use_cassette("queries_batch"):
        results = client.execute_batch([query])
    assert results == expected


def test_named_query(client):
    query = gql("""
        query Planet1 {
          planet(id: "UGxhbmV0OjEw") {
            id
            name
          }
        }
        query Planet2 {
          planet(id: "UGxhbmV0OjEx") {
            id
            name
          }
        }
        """)
    query.operation_name = "Planet2"
    expected = [{"planet": {"id": "UGxhbmV0OjEx", "name": "Geonosis"}}]
    with use_cassette("queries_batch"):
        results = client.execute_batch([query])
    assert results == expected


def test_header_query(client):
    query = gql("""
        query Planet($id: ID!) {
          planet(id: $id) {
            id
            name
          }
        }
        """)
    expected = [{"planet": {"id": "UGxhbmV0OjEx", "name": "Geonosis"}}]
    with use_cassette("queries_batch"):
        results = client.execute_batch(
            [query],
            extra_args={"headers": {"authorization": "xxx-123"}},
        )
    assert results == expected
