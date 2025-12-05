import pathlib
import sys
import zlib

__all__ = ["Git"]

NULL_BYTE = b"\x00"


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

    def create_blob(self, content: str, *, write: bool = True) -> str:
        # Format the blob object
        blob = f"blob {len(content)}\0{content}"
        # Convert to bytes
        blob_bytes = blob.encode()
        # Compress using zlib
        compressed = zlib.compress(blob_bytes)

        # Calculate SHA-1 hash
        import hashlib

        hash_object = hashlib.sha1(blob_bytes)
        hash_value = hash_object.hexdigest()

        if write:
            path = self.objects_folder / hash_value[:2]
            path.mkdir(exist_ok=True)

            with (path / hash_value[2:]).open("wb") as f:
                f.write(compressed)
        return hash_value

    def hash_object(
        self, path: pathlib.Path, *, write: bool = False, pretty_print: bool = True
    ):
        with path.open("r") as f:
            hash_value = self.create_blob(f.read(), write=write)
        if pretty_print:
            sys.stdout.write(hash_value)
        return hash_value

    @classmethod
    def ls_tree(cls, hash_value: str, *, name_only: bool = False):
        raise NotImplementedError

    def write_tree(self, working_directory: pathlib.Path = None):
        working_directory = working_directory or pathlib.Path(".")
        hash_values = []

        for path in working_directory.iterdir():
            if path.name in self.ignore_patterns:
                continue
            if path.is_dir():
                hash_values.extend(self.write_tree(path))
            if path.is_file():
                hash_values.append(self.hash_object(path))

        return hash_values
