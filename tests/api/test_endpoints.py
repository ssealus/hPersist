"""End-to-end API validation through TestClient.

Covers what each endpoint refuses, NOT the happy paths that need upstream
(LLM / PartSurfer / live iLO). Happy paths live in the unit tests with mocks.
"""
from __future__ import annotations

# ── /health, /version ────────────────────────────────────────

def test_health_returns_ok(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_version_includes_version_string(client):
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    j = r.json()
    assert "version" in j
    assert "collector" in j


# ── /insight ─────────────────────────────────────────────────

def test_insight_report_templates_lists_three(client):
    r = client.get("/api/v1/insight/report-templates")
    assert r.status_code == 200
    assert set(r.json()["templates"]) == {"procurement", "firmware", "deprecated"}


def test_insight_run_rejects_empty_inventory_ids(client):
    r = client.post("/api/v1/insight/run", json={"inventory_ids": [], "mode": "summary"})
    assert r.status_code == 422  # pydantic min_length=1


def test_insight_run_rejects_unknown_mode(client):
    r = client.post("/api/v1/insight/run", json={"inventory_ids": ["x"], "mode": "vibes"})
    assert r.status_code == 400
    assert "unknown mode" in r.json()["detail"]


def test_insight_run_analytics_without_question_rejected(client):
    r = client.post("/api/v1/insight/run", json={"inventory_ids": ["x"], "mode": "analytics"})
    assert r.status_code == 400
    assert "question" in r.json()["detail"].lower()


def test_insight_run_reports_with_bad_template_rejected(client):
    r = client.post("/api/v1/insight/run", json={
        "inventory_ids": ["x"], "mode": "reports", "template": "bogus",
    })
    assert r.status_code == 400
    assert "procurement" in r.json()["detail"]  # error lists valid choices


def test_insight_run_stream_rejects_empty_inventory_ids(client):
    r = client.post("/api/v1/insight/run/stream",
                    json={"inventory_ids": [], "mode": "summary"})
    assert r.status_code == 422


# ── /tools ───────────────────────────────────────────────────

def test_partsurfer_search_requires_min_2_chars(client):
    r = client.get("/api/v1/tools/partsurfer/search?q=a")
    assert r.status_code == 422


def test_partsurfer_search_requires_q_param(client):
    r = client.get("/api/v1/tools/partsurfer/search")
    assert r.status_code == 422


def test_redfish_test_endpoints_returns_known_list(client):
    r = client.get("/api/v1/tools/redfish-test/endpoints")
    assert r.status_code == 200
    eps = r.json()
    assert "/redfish/v1/" in eps


# ── /settings (key whitelist) ────────────────────────────────

def test_settings_patch_persists_known_key(client):
    r = client.patch("/api/v1/settings", json={"theme": "light"})
    assert r.status_code == 200
    r2 = client.get("/api/v1/settings")
    assert r2.json().get("theme") == "light"


def test_settings_patch_ignores_unknown_keys(client):
    client.patch("/api/v1/settings", json={"hacker_secret": "owned"})
    r = client.get("/api/v1/settings")
    assert "hacker_secret" not in r.json()


def test_settings_patch_accepts_all_llm_keys(client):
    body = {
        "llm_base_url": "http://x/v1",
        "llm_model": "m",
        "llm_api_key": "k",
        "llm_anonymize": "true",
        "llm_context_level": "compact",
    }
    r = client.patch("/api/v1/settings", json=body)
    assert r.status_code == 200
    got = client.get("/api/v1/settings").json()
    for k, v in body.items():
        assert got[k] == v
