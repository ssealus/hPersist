"""Standalone integrity helpers shipped in the Smart Hands archive."""
from __future__ import annotations

import hashlib
import json
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from nacl import signing


def derive_signing_key(seed: bytes) -> signing.SigningKey:
    return signing.SigningKey(seed[:32].ljust(32, b"\0"))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(slots=True)
class ChainEntry:
    host: str
    payload_hash: str
    prev_hash: str
    chain_hash: str
    signature: str


def build_chain(records: Iterable[tuple[str, dict]], seed: bytes) -> tuple[list[ChainEntry], str]:
    sk = derive_signing_key(seed)
    entries: list[ChainEntry] = []
    prev = "0" * 64
    for host, payload in records:
        payload_hash = sha256_bytes(canonical_json(payload))
        chain_hash = sha256_bytes(f"{prev}|{host}|{payload_hash}".encode())
        sig = sk.sign(chain_hash.encode()).signature.hex()
        entries.append(ChainEntry(host=host, payload_hash=payload_hash, prev_hash=prev, chain_hash=chain_hash, signature=sig))
        prev = chain_hash
    return entries, prev


def write_envelope(envelope: dict, path: Path) -> None:
    """Wrap the envelope JSON in a tar.gz so it can carry a small log too."""
    body = canonical_json(envelope)

    with tarfile.open(path, "w:gz") as tf:
        info = tarfile.TarInfo(name="envelope.json")
        info.size = len(body)
        tf.addfile(info, BytesIO(body))

        manifest = canonical_json({
            "schema": envelope.get("schema"),
            "host_count": envelope.get("host_count"),
            "succeeded": envelope.get("succeeded"),
            "failed": envelope.get("failed"),
            "generated_at": envelope.get("generated_at"),
            "integrity": envelope.get("integrity"),
            "metadata": envelope.get("metadata"),
        })
        mi = tarfile.TarInfo(name="manifest.json")
        mi.size = len(manifest)
        tf.addfile(mi, BytesIO(manifest))
