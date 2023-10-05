from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple, Type


@dataclass
class FileVar:
    f: Any  # str | io.IOBase | aiohttp.StreamReader | AsyncGenerator
    # Add KW_ONLY here once Python 3.9 is deprecated
    filename: Optional[str] = None
    content_type: Optional[str] = None
    streaming: bool = False
    streaming_block_size: int = 64 * 1024


def extract_files(
    variables: Dict, file_classes: Tuple[Type[Any], ...]
) -> Tuple[Dict, Dict]:
    files = {}

    def recurse_extract(path, obj):
        """
        recursively traverse obj, doing a deepcopy, but
        replacing any file-like objects with nulls and
        shunting the originals off to the side.
        """
        nonlocal files
        if isinstance(obj, list):
            nulled_obj = []
            for key, value in enumerate(obj):
                value = recurse_extract(f"{path}.{key}", value)
                nulled_obj.append(value)
            return nulled_obj
        elif isinstance(obj, dict):
            nulled_obj = {}
            for key, value in obj.items():
                value = recurse_extract(f"{path}.{key}", value)
                nulled_obj[key] = value
            return nulled_obj
        elif isinstance(obj, file_classes):
            # extract obj from its parent and put it into files instead.
            name = getattr(obj, "name", None)
            content_type = getattr(obj, "content_type", None)
            files[path] = FileVar(obj, filename=name, content_type=content_type)
            return None
        elif isinstance(obj, FileVar):
            # extract obj from its parent and put it into files instead.
            files[path] = obj
            return None
        else:
            # base case: pass through unchanged
            return obj

    nulled_variables = recurse_extract("variables", variables)

    return nulled_variables, files
