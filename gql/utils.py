"""Utilities to manipulate several python objects."""

import io
from typing import Dict, List, Any, Union


# From this response in Stackoverflow
# http://stackoverflow.com/a/19053800/1072990
def to_camel_case(snake_str):
    components = snake_str.split("_")
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + "".join(x.title() if x else "_" for x in components[1:])


def is_file_like(value: Any) -> bool:
    """Check if a value represents a file like object"""
    return isinstance(value, io.IOBase)


def is_file_like_list(value: Any) -> bool:
    """Check if value is a list and if all items in the list are file-like"""
    return isinstance(value, list) and all(is_file_like(item) for item in value)


def contains_file_like_values(value: Any) -> bool:
    return is_file_like(value) or is_file_like_list(value)


def get_file_variables(
    variables: Dict[str, Any]
) -> Dict[str, Union[io.IOBase, List[io.IOBase]]]:
    return {
        variable: value
        for variable, value in variables.items()
        if contains_file_like_values(value)
    }
