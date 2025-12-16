import binascii
import hashlib
import pathlib
import re
import sys
import zlib
from dataclasses import dataclass
from enum import StrEnum, auto

__all__ = ["Git"]

from operator import attrgetter

from os import PathLike
from typing import Iterator

from app.models.clone import GitClone

NULL_BYTE = b"\x00"


class GitObject(StrEnum):
    BLOB = auto()
    TREE = auto()
    COMMIT = auto()

    @property
    def mode(self):
        match self:
            case GitObject.BLOB:
                return "100644"
            case GitObject.TREE:
                return "40000"
            case _:
                raise ValueError(f"Invalid GitObject: {self}")


@dataclass(frozen=True, kw_only=True)
class TreeEntry:
    mode: bytes
    file_name: bytes
    raw_hash: bytes

    @property
    def hash(self):
        return binascii.hexlify(self.raw_hash).decode()


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
        self,
        working_directory: PathLike = ".",
        *,
        write: bool = True,
        pretty_print: bool = True,
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
                entries.append(f"{mode} {entry.name}".encode() + b"\0" + hash_binary)
            elif entry.is_dir():
                mode = GitObject.TREE.mode  # Directory mode
                hash_value = self.create_tree(entry, write=write, pretty_print=False)
                # Convert hex string to binary
                hash_binary = binascii.unhexlify(hash_value)
                entries.append(f"{mode} {entry.name}".encode() + b"\0" + hash_binary)

        # Combine all entries into a single tree object
        tree_content = b"".join(entries)
        tree_header = f"tree {len(tree_content)}".encode()
        tree_store = tree_header + b"\0" + tree_content

        # Hash and store the tree object
        tree_hash = self.create_hash(tree_store)
        if write:
            self.save_file(tree_hash, tree_store)
        if pretty_print:
            sys.stdout.write(tree_hash)
        return tree_hash

    @staticmethod
    def _parse_tree_content(content: bytes) -> Iterator[TreeEntry]:
        pattern = re.compile(
            rb"""
                    (?P<mode>\d+)
                    \s
                    (?P<file_name>[^\x00]+)
                    \x00
                    (?P<raw_hash>.{20})
                    """,
            re.VERBOSE,
        )
        for match in pattern.finditer(content):
            yield TreeEntry(**match.groupdict())

    def ls_tree(self, hash_value: str, *, name_only: bool = False):
        object_path = self.objects_folder / hash_value[:2] / hash_value[2:]
        with object_path.open("rb") as f:
            data = zlib.decompress(f.read())

        # Split header from content
        header, _, content = data.partition(b"\0")
        if not header.startswith(b"tree "):
            raise ValueError(f"Not a tree object: {header}")

        # Parse entries
        entries = list(self._parse_tree_content(content))
        if name_only:
            # Sort entries by filename before printing
            entries.sort(key=attrgetter("file_name"))
            for entry in entries:
                # Add newline after each filename
                print(entry.file_name.decode() + "\n", end="")
        return entries

    def commit_tree(
        self,
        tree_hash: str,
        message: str,
        *,
        parent: str = "",
        author: str = "Author Name <author@email.com>",
        committer: str = "Committer Name <committer@email.com>",
        timestamp: int = None,
        timezone: str = "-0500",
        pretty_print: bool = True,
    ):
        import time

        if timestamp is None:
            timestamp = int(time.time())

        # Build the commit content
        lines = [
            f"tree {tree_hash}",
        ]
        if parent:
            lines.append(f"parent {parent}")

        lines.append(f"author {author} {timestamp} {timezone}")
        lines.append(f"committer {committer} {timestamp} {timezone}")
        lines.append("")
        lines.append(message)
        commit_content = "\n".join(lines).encode() + b"\n"

        # Create the commit object with proper header
        header = f"commit {len(commit_content)}".encode()
        commit_object = header + NULL_BYTE + commit_content

        # Hash and save
        hash_value = self.create_hash(commit_object)
        self.save_file(hash_value, commit_object)

        if pretty_print:
            sys.stdout.write(hash_value)
        return hash_value

    def clone(self, url: str, working_directory: PathLike = "."):
        work_dir = pathlib.Path(working_directory)
        git_dir = work_dir / ".git"

        # Initialize .git directory structure
        git_dir.mkdir(parents=True, exist_ok=True)
        (git_dir / "objects").mkdir(exist_ok=True)
        (git_dir / "refs").mkdir(exist_ok=True)
        (git_dir / "refs" / "heads").mkdir(exist_ok=True)

        with GitClone(url) as clone:
            pack_data = clone.send_want_request()
            pack_header = clone.parse_pack_header(pack_data)
            objects = clone.parse_pack_objects(pack_data, pack_header.num_objects)
            stored = clone.store_objects(objects, git_dir)

            # Find HEAD commit and checkout
            head_sha = clone.refs["HEAD"].sha1
            commit_obj = stored[head_sha]
            commit_info = clone.parse_commit(commit_obj.data)
            tree_sha = commit_info["tree"]

            clone.checkout(tree_sha, stored, work_dir)

            # Write refs/heads/main and HEAD
            (git_dir / "refs" / "heads" / "main").write_text(f"{head_sha}\n")
            (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
