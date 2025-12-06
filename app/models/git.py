import binascii
import hashlib
import pathlib
import sys
import zlib
from enum import StrEnum, auto

__all__ = ["Git"]

from os import PathLike

from app.utils import chdir

NULL_BYTE = b"\x00"


class GitObject(StrEnum):
    BLOB = "blob"
    TREE = "tree"

    @property
    def mode(self):
        match self:
            case GitObject.BLOB:
                return "100644"
            case GitObject.TREE:
                return "040000"
            case _:
                raise ValueError(f"Invalid GitObject: {self}")


class Git:
    ignore_patterns = {".git", "__pycache__", ".pytest_cache", ".venv", "HEAD"}

    def __init__(self):
        self.git_folder = pathlib.Path(".git")
        self.objects_folder = self.git_folder / "objects"

    @staticmethod
    def init_repo():
        path = pathlib.Path(".")
        dirs = [".git", ".git/objects", ".git/refs"]
        for _dir in dirs:
            new_path = path / _dir
            new_path.mkdir(exist_ok=False, parents=True)
        with pathlib.Path(".git/HEAD").open("w") as f:
            f.write("ref: refs/heads/main\n")
        return

    def cat_file(self, hash_: str, *, pretty_print: bool = False):
        from app.models import Blob

        path = self.objects_folder / hash_[:2] / hash_[2:]
        with path.open("rb") as f:
            data = zlib.decompress(f.read())
        header, _, body = data.partition(NULL_BYTE)
        if pretty_print:
            sys.stdout.write(body.decode())
        return Blob(header=header, body=body)

    @staticmethod
    def compress(data: bytes, *, compressor=zlib.compress) -> bytes:
        return compressor(data)

    @staticmethod
    def create_hash(data: str | bytes, *, hasher=hashlib.sha1) -> str:
        if isinstance(data, str):
            data = data.encode()
        hash_object = hasher(data)
        hash_value = hash_object.hexdigest()
        return hash_value

    def save_file(self, hash_value, data: bytes):
        path = self.objects_folder / hash_value[:2]
        path.mkdir(exist_ok=True)

        compressed_data = self.compress(data)
        with (path / hash_value[2:]).open("wb") as f:
            f.write(compressed_data)
        return hash_value

    def create_blob(self, content: str, *, write: bool = True) -> str:
        blob = f"blob {len(content)}\0{content}"
        hash_value = self.create_hash(blob)
        if write:
            self.save_file(hash_value, blob.encode())
        return hash_value

    def hash_object(
        self,
        path: pathlib.Path,
        *,
        git_object: GitObject = GitObject.BLOB,
        write: bool = False,
        pretty_print: bool = True,
    ):
        with path.open("r") as f:
            match git_object:
                case GitObject.BLOB:
                    hash_value = self.create_blob(f.read(), write=write)
                case GitObject.TREE:
                    hash_value = self.create_tree(path, write=write)
        if pretty_print:
            sys.stdout.write(hash_value)
        return hash_value

    def create_tree(
        self, working_directory: PathLike = ".", *, write: bool = True
    ) -> str:
        entries = []
        dir_path = pathlib.Path(working_directory)

        for entry in sorted(dir_path.iterdir()):
            if entry.name.startswith(".git"):
                continue

            if entry.is_file():
                mode = GitObject.BLOB.mode  # Regular file mode
                hash_value = self.hash_object(
                    entry, git_object=GitObject.BLOB, write=True, pretty_print=False
                )
                # Convert hex string to binary
                hash_binary = binascii.unhexlify(hash_value)
                entries.append(
                    f"{mode} blob {entry.name}".encode() + b"\0" + hash_binary
                )
            elif entry.is_dir():
                mode = GitObject.TREE.mode  # Directory mode
                hash_value = self.create_tree(entry, write=write)
                # Convert hex string to binary
                hash_binary = binascii.unhexlify(hash_value)
                entries.append(
                    f"{mode} tree {entry.name}".encode() + b"\0" + hash_binary
                )

        # Combine all entries into a single tree object
        tree_content = b"".join(entries)
        tree_header = f"tree {len(tree_content)}".encode()
        tree_store = tree_header + b"\0" + tree_content

        # Hash and store the tree object
        tree_hash = self.create_hash(tree_store)
        if write:
            self.save_file(tree_hash, tree_store)
        return tree_hash

    def ls_tree(self, hash_value: str, *, name_only: bool = False):
        # Read and decompress the tree object
        entries = []

        dir_name = self.objects_folder / hash_value[:2]
        with chdir(dir_name):
            file_name = pathlib.Path(hash_value[2:])
            with file_name.open("rb") as f:
                data = zlib.decompress(f.read())

        header, _, tree_data = data.partition(NULL_BYTE)
        kind, data_len = header.decode().split()
        entry_data, _, raw_hash = tree_data.partition(NULL_BYTE)
        mode, entry_kind, name = entry_data.split()
        hash_value = binascii.hexlify(raw_hash).decode()

        entry = {
            "mode": mode.decode(),
            "type": entry_kind.decode(),
            "name": name.decode(),
            "hash": hash_value,
        }
        entries.append(entry)
        return entry
