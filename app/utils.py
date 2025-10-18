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
    return parser


def create_blob(content: str) -> str:
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

    # Create directory structure
    path = pathlib.Path(".git/objects", hash_value[:2])
    path.mkdir(exist_ok=True)

    with (path / hash_value[2:]).open("wb") as f:
        f.write(compressed)
    # Write the compressed blob
    # with open(path / hash_value[2:], 'wb') as f:
    #     f.write(compressed)
    return hash_value
