"""Smart Hands archive — generation produces a verifiable .tar.gz."""
from __future__ import annotations

import hashlib
import json
import tarfile

import pytest


@pytest.fixture
def tmp_data_dir(tmp_path, monkeypatch):
    """Redirect `settings.data_dir` at runtime so the archive lands in tmp."""
    from app.config import settings
    original = settings.data_dir
    settings.data_dir = tmp_path
    (tmp_path / "archives").mkdir()
    yield tmp_path
    settings.data_dir = original


def test_generate_archive_creates_targz_with_meta(tmp_data_dir):
    from app.smart_hands.generator import generate_archive
    ga = generate_archive(
        inventory_name="bench-q1",
        organization="Acme",
        description="quarterly audit",
    )
    assert ga.path.exists()
    assert ga.path.suffix == ".gz"
    assert ga.size_bytes > 0
    assert len(ga.seed) == 64  # 32 bytes hex
    assert ga.expected_script_sha256


def test_generated_archive_contains_collect_py_and_meta(tmp_data_dir):
    from app.smart_hands.generator import generate_archive
    ga = generate_archive(inventory_name="x", organization=None, description=None)

    with tarfile.open(ga.path, "r:gz") as tf:
        names = tf.getnames()
        assert any(n.endswith("collect.py") for n in names)
        assert any(n.endswith("meta.json") for n in names)


def test_meta_json_records_seed_and_script_hash(tmp_data_dir):
    from app.smart_hands.generator import generate_archive
    ga = generate_archive(inventory_name="m", organization="Acme", description=None)

    with tarfile.open(ga.path, "r:gz") as tf:
        meta_member = next(m for m in tf.getmembers() if m.name.endswith("meta.json"))
        meta = json.loads(tf.extractfile(meta_member).read())
    assert meta["integrity_seed"] == ga.seed
    assert meta["expected_script_sha256"] == ga.expected_script_sha256
    assert meta["organization"] == "Acme"


def test_expected_script_sha_matches_template_collect_py(tmp_data_dir):
    """The hash in meta MUST match the real on-disk template — otherwise the
    remote will think the script was tampered with."""
    from app.smart_hands.generator import TEMPLATE_DIR, generate_archive
    expected = hashlib.sha256((TEMPLATE_DIR / "collect.py").read_bytes()).hexdigest()
    ga = generate_archive(inventory_name="h", organization=None, description=None)
    assert ga.expected_script_sha256 == expected


def test_inventory_csv_embedded_when_provided(tmp_data_dir):
    from app.smart_hands.generator import generate_archive
    csv = "ip,hostname,login,password\n10.0.0.1,h-01,root,pw\n"
    ga = generate_archive(inventory_name="i", organization=None, description=None, csv_text=csv)
    with tarfile.open(ga.path, "r:gz") as tf:
        names = tf.getnames()
        inv_csv = [n for n in names if n.endswith("inventory.csv")]
        assert inv_csv
        body = tf.extractfile(inv_csv[0]).read().decode()
        assert "10.0.0.1" in body


def test_archive_name_includes_slugified_inventory(tmp_data_dir):
    from app.smart_hands.generator import generate_archive
    ga = generate_archive(
        inventory_name="Vertex Pharma — Q2 Audit!",
        organization=None,
        description=None,
    )
    assert "vertex-pharma" in ga.path.name.lower()
