import contextlib
import pathlib
import subprocess
from operator import attrgetter

import pytest

from app.main import Git


@pytest.fixture
def change_to_tmp_dir(tmp_path):
    with contextlib.chdir(tmp_path):
        yield tmp_path


@pytest.fixture
def create_git_tree(change_to_tmp_dir):
    """Create a test Git repository with a predefined structure.

    Creates:
        parent_folder/
            ├── file1.txt ("hello")
            └── child_folder/
                └── file2.txt ("world")

    Returns:
        str: Hash value of the created Git tree
    """

    parent_folder = change_to_tmp_dir / "parent_folder"
    parent_folder.mkdir()
    file1 = parent_folder / "file1.txt"
    file1.write_text("hello")
    #
    child_folder = parent_folder / "child_folder"
    child_folder.mkdir()
    file2 = child_folder / "file2.txt"
    file2.write_text("world")

    for cmd in [
        ["git", "init", "."],
        ["git", "add", "."],
    ]:
        result = subprocess.run(
            cmd, cwd=change_to_tmp_dir, capture_output=True, text=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to run git command: {cmd}\n{result.stderr}")

    result = subprocess.run(
        ["git", "write-tree"], cwd=change_to_tmp_dir, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to run git command: {cmd}\n{result.stderr}")
    hash_value = result.stdout.strip()
    if not hash_value or len(hash_value) != 40:
        raise RuntimeError(f"Failed to get tree hash: {hash_value}")

    return hash_value


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

    def test_read_tree(self, create_git_tree):
        git = Git()
        entries = git.ls_tree(create_git_tree)

        # Test that we have exactly one entry (parent_folder)
        assert len(entries) == 1

        # Test parent_folder properties
        parent_entry = entries[0]
        assert parent_entry.mode == b"40000"  # Directory mode
        assert parent_entry.file_name == b"parent_folder"

        # Get the contents of parent_folder
        parent_entries = git.ls_tree(parent_entry.hash)

        # Should have two entries: file1.txt and child_folder
        assert len(parent_entries) == 2

        # Sort entries by filename for consistent testing
        parent_entries.sort(key=attrgetter("file_name"))

        # Test child_folder
        child_folder_entry = parent_entries[0]
        assert child_folder_entry.mode == b"40000"  # Directory mode
        assert child_folder_entry.file_name == b"child_folder"

        # Test file1.txt
        file1_entry = parent_entries[1]
        assert file1_entry.mode == b"100644"  # File mode
        assert file1_entry.file_name == b"file1.txt"

        # Test contents of child_folder
        child_entries = git.ls_tree(child_folder_entry.hash)

        # Should have one file: file2.txt
        assert len(child_entries) == 1
        file2_entry = child_entries[0]
        assert file2_entry.mode == b"100644"  # File mode
        assert file2_entry.file_name == b"file2.txt"

        assert git.cat_file(file1_entry.hash).body == b"hello"
        assert git.cat_file(file2_entry.hash).body == b"world"
