from typing import (
    Any,
    Dict,
    List,
)

from graphql import ExecutionResult

from ...graphql_request import GraphQLRequest
from ..exceptions import (
    TransportProtocolError,
)


def _raise_protocol_error(result_text: str, reason: str) -> None:
    raise TransportProtocolError(
        f"Server did not return a valid GraphQL result: " f"{reason}: " f"{result_text}"
    )


def _validate_answer_is_a_list(results: Any) -> None:
    if not isinstance(results, list):
        _raise_protocol_error(
            str(results),
            "Answer is not a list",
        )


def _validate_data_and_errors_keys_in_answers(results: List[Dict[str, Any]]) -> None:
    for result in results:
        if "errors" not in result and "data" not in result:
            _raise_protocol_error(
                str(results),
                'No "data" or "errors" keys in answer',
            )


def _validate_every_answer_is_a_dict(results: List[Dict[str, Any]]) -> None:
    for result in results:
        if not isinstance(result, dict):
            _raise_protocol_error(str(results), "Not every answer is dict")


def _validate_num_of_answers_same_as_requests(
    reqs: List[GraphQLRequest],
    results: List[Dict[str, Any]],
) -> None:
    if len(reqs) != len(results):
        _raise_protocol_error(
            str(results),
            (
                "Invalid number of answers: "
                f"{len(results)} answers received for {len(reqs)} requests"
            ),
        )


def _answer_to_execution_result(result: Dict[str, Any]) -> ExecutionResult:
    return ExecutionResult(
        errors=result.get("errors"),
        data=result.get("data"),
        extensions=result.get("extensions"),
    )


def get_batch_execution_result_list(
    reqs: List[GraphQLRequest],
    answers: List,
) -> List[ExecutionResult]:

    _validate_answer_is_a_list(answers)
    _validate_num_of_answers_same_as_requests(reqs, answers)
    _validate_every_answer_is_a_dict(answers)
    _validate_data_and_errors_keys_in_answers(answers)

    return [_answer_to_execution_result(answer) for answer in answers]
