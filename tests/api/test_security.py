"""Security regressions — path traversal in SPA fallback + locale endpoint.

Locks in the fix from commit 7dd7c0d so the holes can't reopen silently.
"""
from __future__ import annotations

from urllib.parse import quote


def _body(response) -> str:
    """Decode response.body to a small preview for assertion clarity."""
    return response.text[:400] if hasattr(response, "text") else ""


# ── i18n locale lookup (CodeQL py/path-injection #5) ─────────

def test_locale_happy_path_two_letter_code(client):
    r = client.get("/api/v1/locales/en")
    assert r.status_code == 200
    assert "app" in r.json() or "_meta" in r.json()


def test_locale_rejects_uppercase_two_letter_code(client):
    # `EN` is not allowed by the regex — case-sensitive whitelist.
    r = client.get("/api/v1/locales/EN")
    assert r.status_code == 404


def test_locale_rejects_dotdot_traversal(client):
    # `..%2Fconfig` must NOT escape locales/
    r = client.get("/api/v1/locales/" + quote("../config", safe=""))
    assert r.status_code == 404


def test_locale_rejects_embedded_slash(client):
    r = client.get("/api/v1/locales/" + quote("en/../ru", safe=""))
    assert r.status_code == 404


def test_locale_rejects_long_query(client):
    # Defends against accidentally accepting model names / other long strings.
    r = client.get("/api/v1/locales/" + "a" * 50)
    assert r.status_code == 404


def test_locale_list_returns_known_codes(client):
    r = client.get("/api/v1/locales")
    assert r.status_code == 200
    codes = {loc["code"] for loc in r.json()["locales"]}
    assert "en" in codes
    assert "ru" in codes


# ── SPA fallback (CodeQL py/path-injection #6/#7/#8) ─────────

def test_spa_root_serves_index(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text or "<html" in r.text


def test_spa_serves_real_static_asset(client):
    # styles.css is a real file in frontend/
    r = client.get("/styles.css")
    assert r.status_code == 200


def test_spa_unknown_path_falls_back_to_index(client):
    r = client.get("/missing-nonsense-route")
    assert r.status_code == 200
    assert "<!DOCTYPE html>" in r.text or "<html" in r.text


def test_spa_rejects_traversal_to_repo_root(client):
    # pyproject.toml exists at the repo root — we MUST NOT serve it.
    r = client.get("/" + quote("../pyproject.toml", safe=""))
    assert r.status_code == 200
    # Falls back to index.html (HTML), NOT the toml content
    assert "name = \"hpersist\"" not in r.text
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


def test_spa_rejects_traversal_to_app_source(client):
    r = client.get("/" + quote("../app/config.py", safe=""))
    assert r.status_code == 200
    assert "class Settings" not in r.text
    assert "<html" in r.text.lower() or "<!doctype" in r.text.lower()


# ── Redfish path sanitizer (CodeQL py/full-ssrf) ─────────────

def test_redfish_sanitize_rejects_absolute_url():
    import pytest

    from app.tools.redfish.tester import _sanitize_redfish_path
    with pytest.raises(ValueError, match="absolute URLs"):
        _sanitize_redfish_path("https://evil.example.com/redfish/v1")


def test_redfish_sanitize_rejects_scheme_relative_url():
    import pytest

    from app.tools.redfish.tester import _sanitize_redfish_path
    with pytest.raises(ValueError):
        _sanitize_redfish_path("//evil.example.com/redfish/v1")


def test_redfish_sanitize_normalizes_relative_path():
    from app.tools.redfish.tester import _sanitize_redfish_path
    assert _sanitize_redfish_path("redfish/v1/Systems") == "/redfish/v1/Systems"
    assert _sanitize_redfish_path("/redfish/v1/") == "/redfish/v1/"
    assert _sanitize_redfish_path("") == "/"
    assert _sanitize_redfish_path(None) == "/"  # type: ignore[arg-type]
