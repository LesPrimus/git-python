import contextlib
import os
import pathlib
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

    # ls-tree
    ls_tree_parser = subparsers.add_parser("ls-tree")
    ls_tree_parser.add_argument("--name-only", action="store_true")
    ls_tree_parser.add_argument("hash_value")

    return parser


@contextlib.contextmanager
def chdir(path):
    old_path = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_path)
