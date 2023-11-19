from typing import Any, Iterable, List, Optional, Sized

from graphql import Node


def _node_tree_recursive(
    obj: Any,
    *,
    indent=0,
    ignored_keys=None,
):

    if ignored_keys is None:
        ignored_keys = []

    results = []

    if hasattr(obj, "__slots__"):

        results.append("  " * indent + f"{type(obj).__name__}")

        try:
            keys = obj.keys
        except AttributeError:
            # If the object has no keys attribute, print its repr and return.
            results.append("  " * (indent + 1) + repr(obj))
        else:
            for key in keys:
                if key in ignored_keys:
                    continue
                attr_value = getattr(obj, key, None)
                results.append("  " * (indent + 1) + f"{key}:")
                if isinstance(attr_value, Iterable) and not isinstance(
                    attr_value, (str, bytes)
                ):
                    if isinstance(attr_value, Sized) and len(attr_value) == 0:
                        results.append(
                            "  " * (indent + 2) + f"empty {type(attr_value).__name__}"
                        )
                    else:
                        for item in attr_value:
                            results.append(
                                _node_tree_recursive(
                                    item,
                                    indent=indent + 2,
                                    ignored_keys=ignored_keys,
                                )
                            )
                else:
                    results.append(
                        _node_tree_recursive(
                            attr_value,
                            indent=indent + 2,
                            ignored_keys=ignored_keys,
                        )
                    )
    else:
        results.append("  " * indent + repr(obj))

    return "\n".join(results)


def node_tree(
    obj: Node, *, ignore_loc: bool = True, ignored_keys: Optional[List] = None
):
    """Method which returns a tree of Node elements as a String.

    Useful to debug deep DocumentNode instances created by gql or dsl_gql.

    WARNING: the output of this method is not guaranteed and may change without notice.
    """

    if ignored_keys is None:
        ignored_keys = []

    if ignore_loc:
        # We are ignoring loc attributes by default
        ignored_keys.append("loc")

    return _node_tree_recursive(obj, ignored_keys=ignored_keys)
