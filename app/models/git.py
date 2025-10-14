import pathlib

__all__ = ["Git"]

class Git:
    @classmethod
    def init_repo(cls):
        path = pathlib.Path(".")
        dirs = [".git", ".git/objects", ".git/refs"]
        for _dir in dirs:
            new_path = path / _dir
            new_path.mkdir(exist_ok=False, parents=True)
        with pathlib.Path(".git/HEAD").open("w") as f:
            f.write("ref: refs/heads/main\n")
        return

    def parse_command(self, command):
        match command:
            case "init":
                return self.init_repo()
            case _:
                raise RuntimeError(f"Unknown command #{command}")