"""Integrity helpers — ed25519 signing and hash chain.

Smart Hands archives ship with an integrity *seed* embedded in ``meta.json``.
On the remote host, the collector signs each result with a deterministic
ed25519 key derived from the seed, and builds a hash chain across per-host
records. Tampering with either is detectable on import, while staying
non-fatal — we surface modifications as warnings so the operator can decide.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from nacl import signing
from nacl.encoding import HexEncoder

from app.config import settings


def derive_signing_key(seed: bytes) -> signing.SigningKey:
    """Reproducible signing key from a 32-byte seed."""
    return signing.SigningKey(seed[:32].ljust(32, b"\0"))


def fingerprint(public_key: signing.VerifyKey | bytes) -> str:
    raw = public_key.encode() if isinstance(public_key, signing.VerifyKey) else public_key
    h = hashlib.sha256(raw).hexdigest()
    return f"{h[:4]}…{h[-4:]}"


def get_or_create_instance_key() -> signing.SigningKey:
    """Persistent ed25519 key for this hPersist instance."""
    key_path = settings.data_dir / "instance.key"
    if key_path.exists():
        return signing.SigningKey(key_path.read_bytes(), encoder=HexEncoder)
    sk = signing.SigningKey.generate()
    key_path.write_bytes(sk.encode(encoder=HexEncoder))
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return sk


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
    """Build a hash chain across (host, payload) records and sign each step.

    Returns the per-host entries and the chain head (last chain_hash).
    """
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


def verify_chain(entries: list[dict], payloads: dict[str, dict], seed: bytes) -> tuple[bool, list[str]]:
    """Verify a chain produced by :func:`build_chain`.

    Returns (ok, list_of_issues). Empty issues means a clean pass.
    """
    issues: list[str] = []
    sk = derive_signing_key(seed)
    vk = sk.verify_key
    prev = "0" * 64
    for e in entries:
        payload = payloads.get(e["host"])
        if payload is None:
            issues.append(f"missing payload for host {e['host']}")
            continue
        if sha256_bytes(canonical_json(payload)) != e["payload_hash"]:
            issues.append(f"payload hash mismatch for host {e['host']}")
        expected_chain = sha256_bytes(f"{prev}|{e['host']}|{e['payload_hash']}".encode())
        if expected_chain != e["chain_hash"]:
            issues.append(f"chain hash mismatch at host {e['host']}")
        try:
            vk.verify(e["chain_hash"].encode(), bytes.fromhex(e["signature"]))
        except Exception:
            issues.append(f"signature invalid for host {e['host']}")
        prev = e["chain_hash"]
    return len(issues) == 0, issues
