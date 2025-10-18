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
    ],
)
def test_parser(params, expected):
    parser = get_parser()
    args = parser.parse_args(params)
    assert args == expected
