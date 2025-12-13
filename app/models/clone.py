import re
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
    def __init__(self, repo_url: str, http_client: httpx.Client = None):
        self.repo_url = str(repo_url)
        self.http_client = http_client or httpx.Client()

    def __enter__(self):
        self.http_client.__enter__()
        self.refs, self.capabilities = RefParser.parse_refs(self._fetch_refs())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.http_client.__exit__(exc_type, exc_val, exc_tb)

    def _fetch_refs(self):
        discover_url = f"{self.repo_url}/info/refs?service=git-upload-pack"
        response = self.http_client.get(discover_url)
        response.raise_for_status()
        return response.text.splitlines()

    @staticmethod
    def format_pkt_line(payload: str | bytes) -> bytes:
        if isinstance(payload, str):
            payload = payload.encode()

        # Length includes the 4-byte prefix itself
        length = len(payload) + 4
        # Format as 4-byte hex (lowercase)
        hex_length = f"{length:04x}"
        return hex_length.encode() + payload

    def send_want_request(self):
        caps = " ".join(self.capabilities) if self.capabilities else ""

        body_parts = [
            self.format_pkt_line(f"want {self.refs['HEAD'].sha1} {caps}\n"),
            b"0000",
            self.format_pkt_line("done\n"),
        ]

        # Combine all parts
        request_body = b"".join(body_parts)

        # Send POST request
        upload_pack_url = f"{self.repo_url}/git-upload-pack"
        headers = {
            "Content-Type": "application/x-git-upload-pack-request",
        }

        response = self.http_client.post(
            upload_pack_url,
            content=request_body,
            headers=headers,
        )
        print(response.content)
        return response


if __name__ == "__main__":
    with GitClone(DEFAULT_URL) as clone:
        clone.send_want_request()
