import hashlib
import re
import struct
import zlib
from dataclasses import dataclass
from functools import cache
from pprint import pprint

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


@dataclass
class PackHeader:
    version: int
    num_objects: int

    @classmethod
    def from_bytes(cls, data: bytes):
        version, num_objects = struct.unpack('>II', data[4:12])
        return cls(version, num_objects)

@dataclass
class PackObject:
    type: int
    size: int
    data: bytes
    pack_offset: int = 0  # offset in pack file where this object starts


# Object type constants
OBJ_COMMIT = 1
OBJ_TREE = 2
OBJ_BLOB = 3
OBJ_TAG = 4
OBJ_OFS_DELTA = 6
OBJ_REF_DELTA = 7

TYPE_NAMES = {
    OBJ_COMMIT: "commit",
    OBJ_TREE: "tree",
    OBJ_BLOB: "blob",
    OBJ_TAG: "tag",
}


def compute_sha1(obj_type: int, data: bytes) -> str:
    """Compute git object SHA-1."""
    type_name = TYPE_NAMES[obj_type]
    header = f"{type_name} {len(data)}\x00".encode()
    return hashlib.sha1(header + data).hexdigest()


def read_delta_size(delta: bytes, offset: int) -> tuple[int, int]:
    """Read size varint from delta header."""
    size = 0
    shift = 0
    while True:
        byte = delta[offset]
        size |= (byte & 0x7F) << shift
        offset += 1
        if not (byte & 0x80):
            break
        shift += 7
    return size, offset


def apply_delta(base: bytes, delta: bytes) -> bytes:
    """Apply delta instructions to base object."""
    offset = 0
    _base_size, offset = read_delta_size(delta, offset)
    _result_size, offset = read_delta_size(delta, offset)

    result = bytearray()
    while offset < len(delta):
        cmd = delta[offset]
        offset += 1

        if cmd & 0x80:  # Copy from base
            copy_offset = 0
            copy_size = 0
            if cmd & 0x01:
                copy_offset |= delta[offset]
                offset += 1
            if cmd & 0x02:
                copy_offset |= delta[offset] << 8
                offset += 1
            if cmd & 0x04:
                copy_offset |= delta[offset] << 16
                offset += 1
            if cmd & 0x08:
                copy_offset |= delta[offset] << 24
                offset += 1
            if cmd & 0x10:
                copy_size |= delta[offset]
                offset += 1
            if cmd & 0x20:
                copy_size |= delta[offset] << 8
                offset += 1
            if cmd & 0x40:
                copy_size |= delta[offset] << 16
                offset += 1
            if copy_size == 0:
                copy_size = 0x10000
            result.extend(base[copy_offset:copy_offset + copy_size])
        elif cmd:  # Insert literal (cmd = number of bytes)
            result.extend(delta[offset:offset + cmd])
            offset += cmd

    return bytes(result)


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
        body_parts = [
            self.format_pkt_line(f"want {self.refs['HEAD'].sha1}"),
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
        data = response.content
        if data.startswith(b"0008NAK\n"):
            return data[8:]
        return response.content

    def parse_pack_header(self, data: bytes) -> PackHeader:
        """Parse pack file header, return (version, num_objects)."""
        return PackHeader.from_bytes(data)

    def parse_pack_objects(self, data: bytes, num_objects: int) -> list[PackObject]:
        offset = 12  # skip header
        objects = []
        objects_by_offset = {}  # for ofs_delta lookup
        objects_by_sha1 = {}    # for ref_delta lookup

        # First pass: parse all objects
        for _ in range(num_objects):
            obj_start = offset

            # Read variable-length header
            byte = data[offset]
            obj_type = (byte >> 4) & 0x07
            size = byte & 0x0F
            shift = 4
            offset += 1

            while byte & 0x80:  # continue bit set
                byte = data[offset]
                size |= (byte & 0x7F) << shift
                shift += 7
                offset += 1

            # Handle delta base references
            delta_base_offset = None
            delta_base_sha1 = None

            if obj_type == OBJ_OFS_DELTA:
                # Read negative offset (variable-length encoding)
                byte = data[offset]
                delta_base_offset = byte & 0x7F
                offset += 1
                while byte & 0x80:
                    byte = data[offset]
                    delta_base_offset = ((delta_base_offset + 1) << 7) | (byte & 0x7F)
                    offset += 1
                delta_base_offset = obj_start - delta_base_offset

            elif obj_type == OBJ_REF_DELTA:
                # Read 20-byte base SHA-1
                delta_base_sha1 = data[offset:offset + 20].hex()
                offset += 20

            # Decompress zlib data
            decompressor = zlib.decompressobj()
            decompressed = decompressor.decompress(data[offset:])
            offset += len(data[offset:]) - len(decompressor.unused_data)

            obj = PackObject(obj_type, size, decompressed, obj_start)
            obj._delta_base_offset = delta_base_offset
            obj._delta_base_sha1 = delta_base_sha1

            objects.append(obj)
            objects_by_offset[obj_start] = obj

            # Index non-delta objects by SHA-1
            if obj_type in TYPE_NAMES:
                sha1 = compute_sha1(obj_type, decompressed)
                objects_by_sha1[sha1] = obj

        # Second pass: resolve deltas
        def resolve(obj: PackObject) -> PackObject:
            if obj.type == OBJ_OFS_DELTA:
                base_obj = resolve(objects_by_offset[obj._delta_base_offset])
                resolved_data = apply_delta(base_obj.data, obj.data)
                obj.data = resolved_data
                obj.type = base_obj.type
                obj.size = len(resolved_data)
            elif obj.type == OBJ_REF_DELTA:
                base_obj = resolve(objects_by_sha1[obj._delta_base_sha1])
                resolved_data = apply_delta(base_obj.data, obj.data)
                obj.data = resolved_data
                obj.type = base_obj.type
                obj.size = len(resolved_data)
            return obj

        for obj in objects:
            resolve(obj)

        return objects


if __name__ == "__main__":
    with GitClone(DEFAULT_URL) as clone:
        pack_data = clone.send_want_request()
    pack_header = clone.parse_pack_header(pack_data)
    objects = clone.parse_pack_objects(pack_data, pack_header.num_objects)
    pprint(objects)
