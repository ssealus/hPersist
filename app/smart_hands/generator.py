"""Smart Hands archive generator.

Packs the template directory + a per-instance `meta.json` (seed and
expected `collect.py` sha256) + optional inventory CSV into one tarball.
The remote signs results with a key derived from the seed; the processor
later verifies signatures and checks for script-tampering.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import secrets
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app import __version__ as APP_VERSION
from app.config import settings
from app.core.integrity import canonical_json, sha256_bytes
from app.network.csv_parser import parse_csv, template_csv

TEMPLATE_DIR = Path(__file__).resolve().parent / "template"


@dataclass(slots=True)
class GeneratedArchive:
    path: Path
    sha256: str
    size_bytes: int
    seed: str
    expected_script_sha256: str
    file_list: list[str]


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    return (s or "untitled")[:40]


def generate_archive(
    *,
    inventory_name: str,
    organization: str | None,
    description: str | None,
    created_by: str | None = None,
    csv_text: str | None = None,
    inventory_id: str | None = None,
) -> GeneratedArchive:
    seed = secrets.token_bytes(32).hex()
    out_dir = settings.data_dir / "archives"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = _slugify(inventory_name)
    archive_name = f"hpersist-collector-{slug}-{ts}.tar.gz"
    archive_path = out_dir / archive_name

    # hash collect.py first — meta.json embeds it; the remote re-hashes its own
    # copy and compares, surfacing tampering as `script-modified`
    collect_py_bytes = (TEMPLATE_DIR / "collect.py").read_bytes()
    expected_script_sha = sha256_bytes(collect_py_bytes)

    meta = {
        "schema": "hpersist/v1",
        "name": inventory_name,
        "organization": organization,
        "description": description,
        "created_by": created_by,
        "inventory_id": inventory_id,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator_version": f"hPersist {APP_VERSION}",
        "integrity_seed": seed,
        "expected_script_sha256": expected_script_sha,
    }
    meta_bytes = canonical_json(meta)

    inventory_bytes = (
        csv_text.encode("utf-8")
        if csv_text
        else template_csv().encode("utf-8")
    )

    file_list: list[str] = []

    def _add_bytes(tf: tarfile.TarFile, arcname: str, data: bytes) -> None:
        info = tarfile.TarInfo(name=arcname)
        info.size = len(data)
        info.mtime = int(datetime.now(timezone.utc).timestamp())
        info.mode = 0o644
        tf.addfile(info, io.BytesIO(data))
        file_list.append(arcname)

    def _add_path(tf: tarfile.TarFile, src: Path, arc_root: str) -> None:
        for p in sorted(src.rglob("*")):
            if p.name == "__pycache__" or "__pycache__" in p.parts:
                continue
            if p.is_file():
                rel = p.relative_to(src).as_posix()
                arcname = f"{arc_root}/{rel}"
                info = tarfile.TarInfo(name=arcname)
                data = p.read_bytes()
                info.size = len(data)
                info.mtime = int(p.stat().st_mtime)
                info.mode = 0o755 if p.suffix == ".py" and p.name == "collect.py" else 0o644
                tf.addfile(info, io.BytesIO(data))
                file_list.append(arcname)

    arc_root = "hpersist-collector"
    with tarfile.open(archive_path, "w:gz") as tf:
        _add_bytes(tf, f"{arc_root}/meta.json", meta_bytes)
        _add_bytes(tf, f"{arc_root}/inventory.csv", inventory_bytes)
        _add_bytes(tf, f"{arc_root}/README.md", (TEMPLATE_DIR / "README.md").read_bytes())
        _add_bytes(tf, f"{arc_root}/requirements.txt", (TEMPLATE_DIR / "requirements.txt").read_bytes())
        _add_bytes(tf, f"{arc_root}/collect.py", collect_py_bytes)
        _add_path(tf, TEMPLATE_DIR / "hpersist_collector", f"{arc_root}/hpersist_collector")

    raw = archive_path.read_bytes()
    return GeneratedArchive(
        path=archive_path,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
        seed=seed,
        expected_script_sha256=expected_script_sha,
        file_list=sorted(file_list),
    )


def preview_csv(csv_text: str) -> dict:
    """Validate a CSV the user wants to bake into the archive."""
    return parse_csv(csv_text).summary()
