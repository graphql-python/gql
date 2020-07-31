"""Utilities to manipulate several python objects."""

import io
from typing import Dict, List, Any, Union, Tuple


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


def extract_files(variables: dict) -> Tuple[dict, dict, list]:
    files = {}

    def recurse_extract(path, obj):
        """
        recursively traverse obj, doing a deepcopy, but
        replacing any file-like objects with nulls and
        shunting the originals off to the side.
        """
        nonlocal files
        if type(obj) is list:
            nulled_obj = []
            for key, value in enumerate(obj):
                value = recurse_extract(f"{path}.{key}", value)
                nulled_obj.append(value)
            # TODO: merge this with dict case below. somehow.
            return nulled_obj
        elif type(obj) is dict:
            nulled_obj = {}
            for key, value in obj.items():
                value = recurse_extract(f"{path}.{key}", value)
                nulled_obj[key] = value
            return nulled_obj
        elif is_file_like(obj):
            # extract obj from its parent and put it into files instead.
            files[path] = obj
            return None
        else:
            # base case: pass through unchanged
            return obj

    nulled_variables = recurse_extract("variables", variables)

    return nulled_variables, files