from argparse import ArgumentParser

from app.models import Git


def get_args():
    parser = ArgumentParser()
    parser.add_argument("command")
    return parser.parse_args()



def main():
    args = get_args()
    git = Git()
    git.parse_command(args.command)


if __name__ == "__main__":
    main()
