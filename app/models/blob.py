from dataclasses import dataclass

__all__ = ["Blob"]


@dataclass(frozen=True, kw_only=True)
class Blob:
    header: bytes
    body: bytes


@dataclass(frozen=True, kw_only=True)
class Tree:
    entries: list[Blob]
