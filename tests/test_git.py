import contextlib
import pathlib

import pytest

from app.main import Git


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
        hash_value = git.create_blob("some content")
        blob = git.cat_file(hash_value)
        assert blob.header == f"blob {len(blob.body)}".encode()
        assert blob.body == b"some content"

    @pytest.mark.parametrize("write", [True, False])
    @pytest.mark.parametrize(
        "content, expected_hash_value",
        [("hello world\n", "3b18e512dba79e4c8300dd08aeb37f8e728b8dad")],
    )
    def test_hash_object(
        self, change_to_tmp_dir, content, expected_hash_value, write, capsys
    ):
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

    def test_write_tree(self, change_to_tmp_dir):
        git = Git()
        git.init_repo()
        #
        parent_dir = change_to_tmp_dir / "parent_dir"
        parent_dir.mkdir()
        file1 = parent_dir / "file1.txt"
        file1.write_text("hello")
        #
        child_dir = parent_dir / "child_dir"
        child_dir.mkdir()
        file2 = child_dir / "file2.txt"
        file2.write_text("World")
        #
        hash_values = git.write_tree()

        git.ls_tree(hash_values, name_only=True)
        assert 0
