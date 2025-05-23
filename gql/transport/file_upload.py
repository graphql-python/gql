import io
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple, Type


class FileVar:
    def __init__(
        self,
        f: Any,  # str | io.IOBase | aiohttp.StreamReader | AsyncGenerator
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        streaming: bool = False,
        streaming_block_size: int = 64 * 1024,
    ):
        self.f = f
        self.filename = filename
        self.content_type = content_type
        self.streaming = streaming
        self.streaming_block_size = streaming_block_size

        self._file_opened: bool = False

    def open_file(
        self,
        transport_supports_streaming: bool = False,
    ) -> None:
        assert self._file_opened is False

        if self.streaming:
            assert (
                transport_supports_streaming
            ), "streaming not supported on this transport"
            self._make_file_streamer()
        else:
            if isinstance(self.f, str):
                if self.filename is None:
                    # By default we set the filename to the basename
                    # of the opened file
                    self.filename = os.path.basename(self.f)
                self.f = open(self.f, "rb")
                self._file_opened = True

    def close_file(self) -> None:
        if self._file_opened:
            assert isinstance(self.f, io.IOBase)
            self.f.close()
            self._file_opened = False

    def _make_file_streamer(self) -> None:
        assert isinstance(self.f, str), "streaming option needs a filepath str"

        import aiofiles

        async def file_sender(file_name):
            async with aiofiles.open(file_name, "rb") as f:
                while chunk := await f.read(self.streaming_block_size):
                    yield chunk

        self.f = file_sender(self.f)


def open_files(
    filevars: List[FileVar],
    transport_supports_streaming: bool = False,
) -> None:

    for filevar in filevars:
        filevar.open_file(transport_supports_streaming=transport_supports_streaming)


def close_files(filevars: List[FileVar]) -> None:
    for filevar in filevars:
        filevar.close_file()


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
