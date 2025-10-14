import os
import pathlib
import shutil

import pytest

from app.main import Git


@pytest.fixture
def cleanup():
    yield
    if os.path.exists(".git"):
        shutil.rmtree(".git")


class TestGit:
    def test_init_repo(self, cleanup):
        git = Git()
        git.init_repo()
        for _dir in [".git", ".git/objects", ".git/refs"]:
            assert pathlib.Path(_dir).exists()
        with pathlib.Path(".git/HEAD").open("r") as f:
            assert f.read() == "ref: refs/heads/main\n"
