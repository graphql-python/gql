"""Utilities to manipulate several python objects."""

from typing import List


# From this response in Stackoverflow
# http://stackoverflow.com/a/19053800/1072990
def to_camel_case(snake_str):
    components = snake_str.split("_")
    # We capitalize the first letter of each component except the first one
    # with the 'title' method and join them together.
    return components[0] + "".join(x.title() if x else "_" for x in components[1:])


def str_first_element(errors: List) -> str:
    try:
        first_error = errors[0]
    except (KeyError, TypeError):
        first_error = errors

    return str(first_error)
