import io
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Type


@dataclass
class FileVar:
    f: Any  # str | io.IOBase | aiohttp.StreamReader | AsyncGenerator
    # Add KW_ONLY here once Python 3.9 is deprecated
    filename: Optional[str] = None
    content_type: Optional[str] = None
    streaming: bool = False
    streaming_block_size: int = 64 * 1024


FILE_UPLOAD_DOCS = "https://gql.readthedocs.io/en/latest/usage/file_upload.html"


def extract_files(
    variables: Dict, file_classes: Tuple[Type[Any], ...]
) -> Tuple[Dict, Dict[str, FileVar]]:
    files: Dict[str, FileVar] = {}

    def recurse_extract(path, obj):
        """
        recursively traverse obj, doing a deepcopy, but
        replacing any file-like objects with nulls and
        shunting the originals off to the side.
        """
        nonlocal files
        if isinstance(obj, list):
            nulled_list = []
            for key, value in enumerate(obj):
                value = recurse_extract(f"{path}.{key}", value)
                nulled_list.append(value)
            return nulled_list
        elif isinstance(obj, dict):
            nulled_dict = {}
            for key, value in obj.items():
                value = recurse_extract(f"{path}.{key}", value)
                nulled_dict[key] = value
            return nulled_dict
        elif isinstance(obj, file_classes):
            # extract obj from its parent and put it into files instead.
            warnings.warn(
                "Not using FileVar for file upload is deprecated. "
                f"See {FILE_UPLOAD_DOCS} for details.",
                DeprecationWarning,
            )
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


def open_files(filevars: List[FileVar]) -> None:

    for filevar in filevars:
        assert isinstance(filevar, FileVar)

        if isinstance(filevar.f, str):
            filevar.f = open(filevar.f, "rb")


def close_files(filevars: List[FileVar]) -> None:
    for filevar in filevars:
        assert isinstance(filevar, FileVar)

        if isinstance(filevar.f, io.IOBase):
            filevar.f.close()
