from app.models import Git
from app.utils import get_parser


def main():
    git = Git()
    parser = get_parser()
    args = parser.parse_args()
    match args.command:
        case "init":
            return git.init_repo()
        case "cat-file":
            return git.cat_file(args.hash, pretty_print=args.pretty_print)
        case "hash-object":
            return git.hash_object(args.path, write=args.write)
        case "ls-tree":
            return git.ls_tree(args.hash_value, name_only=args.name_only)
        case "write-tree":
            return git.create_tree()
        case "commit-tree":
            return git.commit_tree(args.tree_hash, args.message, parent=args.parent)
        case "clone":
            return git.clone(args.url, args.work_dir)
        case _:
            raise RuntimeError(f"Unknown command #{args.command}")


if __name__ == "__main__":
    main()
