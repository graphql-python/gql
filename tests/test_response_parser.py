"""Tests for the GraphQL Response Parser.

These tests are worthless until I have a schema I can work with.
"""
import copy
from gql.response_parser import ResponseParser


class Capitalize():
    def parse_value(self, value: str):
        return value.upper();

def test_scalar_type_name_for_scalar_field_returns_name(gql_schema):
    parser = ResponseParser(gql_schema)
    schema_obj = gql_schema.get_type_map().get('Wallet')

    assert parser._get_scalar_type_name(schema_obj.fields['balance']) == 'Money'


def test_scalar_type_name_for_non_scalar_field_returns_none(gql_schema):
    parser = ResponseParser(gql_schema)
    schema_obj = gql_schema.get_type_map().get('Wallet')

    assert parser._get_scalar_type_name(schema_obj.fields['user']) is None

def test_lookup_scalar_type(gql_schema):
    parser = ResponseParser(gql_schema)

    assert parser._lookup_scalar_type(["wallet"]) is None
    assert parser._lookup_scalar_type(["searchWallets"]) is None
    assert parser._lookup_scalar_type(["wallet", "balance"]) == 'Money'
    assert parser._lookup_scalar_type(["searchWallets", "balance"]) == 'Money'
    assert parser._lookup_scalar_type(["wallet", "name"]) == 'String'
    assert parser._lookup_scalar_type(["wallet", "invalid"]) is None

def test_lookup_scalar_type_in_mutation(gql_schema):
    parser = ResponseParser(gql_schema)

    assert parser._lookup_scalar_type(["manualWithdraw", "agentTransaction"]) is None
    assert parser._lookup_scalar_type(["manualWithdraw", "agentTransaction", "amount"]) == 'Money'

def test_parse_response(gql_schema):
    custom_scalars = {
        'Money': Capitalize
    }
    parser = ResponseParser(gql_schema, custom_scalars)

    response = {
        'wallet': {
            'id': 'some_id',
            'name': 'U1_test',
        }
    }

    expected = {
        'wallet': {
            'id': 'some_id',
            'name': 'U1_test',
        }
    }

    assert parser.parse(response) == expected
    assert response['wallet']['balance'] == 'CFA 3850'

def test_parse_response_containing_list(gql_schema):
    custom_scalars = {
        'Money': M
    }
    parser = ResponseParser(gql_schema, custom_scalars)

    response = {
        "searchWallets": [
            {
                "id": "W_wz518BXTDJuQ",
                "name": "U2_test",
                "balance": "CFA 4148"
            },
            {
                "id": "W_uOe9fHPoKO21",
                "name": "Agent_test",
                "balance": "CFA 2641"
            }
        ]
    }

    expected = copy.deepcopy(response)
    expected['searchWallets'][0]['balance'] = M("CFA", "4148")
    expected['searchWallets'][1]['balance'] = M("CFA", "2641")

    result = parser.parse(response)

    assert result == expected
    assert response['searchWallets'][0]['balance'] == "CFA 4148"
    assert response['searchWallets'][1]['balance'] == "CFA 2641"