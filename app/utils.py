import pathlib
import zlib
from argparse import ArgumentParser


def get_parser():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    # init
    _init_parser = subparsers.add_parser("init")

    # cat-file
    cat_file_parser = subparsers.add_parser("cat-file")
    cat_file_parser.add_argument(
        "-p", "--pretty-print", action="store_true", help="pretty print"
    )
    cat_file_parser.add_argument(
        "hash",
    )

    # hash_object
    hash_object_parser = subparsers.add_parser("hash-object")
    hash_object_parser.add_argument("path", type=pathlib.Path)
    hash_object_parser.add_argument("-w", "--write", action="store_true")
    return parser


def create_blob(content: str, *, write: bool = True) -> str:
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
        # Create directory structure
        path = pathlib.Path(".git/objects", hash_value[:2])
        path.mkdir(exist_ok=True)

        with (path / hash_value[2:]).open("wb") as f:
            f.write(compressed)
    return hash_value
