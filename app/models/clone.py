import re
from functools import cached_property
from dataclasses import dataclass

DEFAULT_URL = "https://github.com/octocat/Hello-World"

import httpx

REGEX = re.compile(
    r"""
(.{4})  # Length
(.{40}) # hash
\s
(.+)    # name
""",
    re.VERBOSE,
)


@dataclass
class GitRef:
    length: int
    sha1: str
    ref_name: str

    @classmethod
    def from_line(cls, line: str):
        match = REGEX.match(line)
        str_len, sha1, ref_name = match.groups()
        length = int(str_len, 16)
        return cls(length, sha1, ref_name)


class RefParser:
    @staticmethod
    def parse_refs(refs_lines: list[str]):
        refs = {}
        capabilities = []
        for line in refs_lines:
            if line == "0000":
                continue
            if "service" in line:
                continue
            if (null_bite := "\x00") in line:
                ref_part, _, capabilities_part = line.partition(null_bite)
                ref_part = ref_part[4:]
                capabilities.extend(capabilities_part.split())
            else:
                ref_part = line
            ref_obj = GitRef.from_line(ref_part)
            refs[ref_obj.ref_name] = ref_obj
        return refs, capabilities


class GitClone:
    def __init__(self, repo_url: str, http_client: httpx.Client = httpx.Client()):
        self.repo_url = str(repo_url)
        self.http_client = http_client
        self.capabilities = []
        self.refs = {}
        self.parse_refs()

    @cached_property
    def get_refs(self):
        discover_url = f"{self.repo_url}/info/refs?service=git-upload-pack"
        with self.http_client as client:
            response = client.get(discover_url)
            response.raise_for_status()
        return response.text.splitlines()

    def parse_refs(self):
        print(RefParser.parse_refs(self.get_refs))


if __name__ == "__main__":
    clone = GitClone(DEFAULT_URL)
    clone.parse_refs()
