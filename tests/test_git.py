import contextlib
import pathlib

import pytest

from app.main import Git
from app.utils import create_blob

@pytest.fixture
def change_to_tmp_dir(tmp_path):
    with contextlib.chdir(tmp_path):
        yield


class TestGit:
    def test_init_repo(self, change_to_tmp_dir):
        git = Git()
        git.init_repo()
        for _dir in [".git", ".git/objects", ".git/refs"]:
            assert pathlib.Path(_dir).exists()
        with pathlib.Path(".git/HEAD").open("r") as f:
            assert f.read() == "ref: refs/heads/main\n"

    def test_cat_file(self, change_to_tmp_dir):
        git = Git()
        git.init_repo()
        hash_value = create_blob("some content")
        blob = git.cat_file(hash_value)
        assert blob.header == f"blob {len(blob.body)}".encode()
        assert blob.body == b"some content"

    def test_hash_object(self, change_to_tmp_dir):
        git = Git()
        git.init_repo()
