import pathlib
import sys
import zlib

__all__ = ["Git"]

from app.utils import create_blob

NULL_BYTE = b"\x00"


class Git:
    @classmethod
    def init_repo(cls):
        path = pathlib.Path(".")
        dirs = [".git", ".git/objects", ".git/refs"]
        for _dir in dirs:
            new_path = path / _dir
            new_path.mkdir(exist_ok=False, parents=True)
        with pathlib.Path(".git/HEAD").open("w") as f:
            f.write("ref: refs/heads/main\n")
        return

    @classmethod
    def cat_file(cls, hash_: str, *, pretty_print: bool = False):
        from app.models import Blob

        path = pathlib.Path(".git", "objects", hash_[:2], hash_[2:])
        with path.open("rb") as f:
            data = zlib.decompress(f.read())
        header, _, body = data.partition(NULL_BYTE)
        if pretty_print:
            sys.stdout.write(body.decode())
        return Blob(header=header, body=body)

    @classmethod
    def hash_object(cls, path: pathlib.Path, *, write: bool = False, pretty_print: bool = True):
        with path.open("r") as f:
            hash_value = create_blob(f.read(), write=write)
        if pretty_print:
            sys.stdout.write(hash_value)
        return hash_value
