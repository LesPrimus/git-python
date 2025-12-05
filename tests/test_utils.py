import pathlib
from argparse import Namespace

import pytest

from app.main import get_parser


@pytest.mark.parametrize(
    "params, expected",
    [
        (["init"], Namespace(command="init")),
        (
            ["cat-file", "some_hash"],
            Namespace(command="cat-file", hash="some_hash", pretty_print=False),
        ),
        (
            ["cat-file", "-p", "some_hash"],
            Namespace(command="cat-file", hash="some_hash", pretty_print=True),
        ),
        (
            ["hash-object", "some_file.txt"],
            Namespace(
                command="hash-object", path=pathlib.Path("some_file.txt"), write=False
            ),
        ),
        (
            ["hash-object", "-w", "some_file.txt"],
            Namespace(
                command="hash-object", path=pathlib.Path("some_file.txt"), write=True
            ),
        ),
        (
            ["ls-tree", "some_hash"],
            Namespace(command="ls-tree", name_only=False, hash_value="some_hash"),
        ),
        (
            [
                "ls-tree",
                "--name-only",
                "some_hash",
            ],
            Namespace(command="ls-tree", name_only=True, hash_value="some_hash"),
        ),
    ],
)
def test_parser(params, expected):
    parser = get_parser()
    args = parser.parse_args(params)
    assert args == expected
