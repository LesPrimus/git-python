import contextlib
import pathlib

import pytest

from app.main import Git
from app.utils import create_blob


@pytest.fixture
def change_to_tmp_dir(tmp_path):
    with contextlib.chdir(tmp_path):
        yield tmp_path


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

    @pytest.mark.parametrize("write", [True, False])
    @pytest.mark.parametrize(
        "content, expected_hash_value",
        [("hello world\n", "3b18e512dba79e4c8300dd08aeb37f8e728b8dad")],
    )
    def test_hash_object(self, change_to_tmp_dir, content, expected_hash_value, write, capsys):
        git = Git()
        git.init_repo()
        tmp_file = change_to_tmp_dir / "file.txt"
        tmp_file.write_text(content)
        hash_value = git.hash_object(tmp_file, write=write)
        assert hash_value == expected_hash_value
        assert len(hash_value) == 40
        expected_path = (
            change_to_tmp_dir / ".git/objects" / hash_value[:2] / hash_value[2:]
        )
        assert expected_path.exists() == write
        assert capsys.readouterr().out == hash_value
