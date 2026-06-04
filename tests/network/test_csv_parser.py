"""CSV inventory parser — happy paths, fatal errors, per-row validation."""
from __future__ import annotations

from app.network.csv_parser import parse_csv, template_csv

# ── Fatal errors (block the entire file) ─────────────────────

def test_empty_text_is_fatal():
    r = parse_csv("")
    assert r.fatal
    assert r.rows == []


def test_missing_required_column_is_fatal():
    r = parse_csv("ip,login\n10.0.0.1,root\n")  # no password column
    assert any("missing required columns" in m for m in r.fatal)
    assert "password" in r.fatal[0]


def test_header_case_insensitive():
    r = parse_csv("IP,Hostname,LOGIN,Password\n10.0.0.1,h1,root,p\n")
    assert not r.fatal
    assert r.summary()["ok"] == 1


# ── Per-row validation ───────────────────────────────────────

def test_well_formed_row_is_ok():
    r = parse_csv("ip,hostname,login,password\n10.0.0.1,h1,root,pw\n")
    assert r.summary() == {"total": 1, "ok": 1, "warn": 0, "err": 0, "fatal": []}
    row = r.rows[0]
    assert row.ip == "10.0.0.1"
    assert row.hostname == "h1"
    assert row.login == "root"
    assert row.password == "pw"


def test_blank_hostname_is_optional():
    r = parse_csv("ip,hostname,login,password\n10.0.0.1,,root,pw\n")
    assert r.summary()["ok"] == 1
    assert r.rows[0].hostname is None


def test_invalid_ip_marked_err():
    r = parse_csv("ip,login,password\n999.999.999.999,root,pw\n")
    assert r.rows[0].status == "err"
    assert "invalid" in r.rows[0].message.lower()


def test_missing_ip_marked_err():
    r = parse_csv("ip,login,password\n,root,pw\n")
    assert r.rows[0].status == "err"
    assert "missing ip" in r.rows[0].message.lower()


def test_missing_login_marked_err():
    r = parse_csv("ip,login,password\n10.0.0.1,,pw\n")
    assert r.rows[0].status == "err"
    assert "login" in r.rows[0].message.lower()


def test_missing_password_marked_err():
    r = parse_csv("ip,login,password\n10.0.0.1,root,\n")
    assert r.rows[0].status == "err"
    assert "password" in r.rows[0].message.lower()


def test_duplicate_ip_warns_not_errors():
    r = parse_csv(
        "ip,login,password\n"
        "10.0.0.1,root,pw\n"
        "10.0.0.1,admin,pw2\n"
    )
    statuses = [row.status for row in r.rows]
    assert statuses == ["ok", "warn"]
    assert "duplicate" in r.rows[1].message.lower()


def test_summary_aggregates_counts():
    r = parse_csv(
        "ip,login,password\n"
        "10.0.0.1,root,pw\n"      # ok
        "10.0.0.1,root,pw\n"      # warn (dup)
        ",root,pw\n"              # err (no ip)
        "10.0.0.2,,pw\n"          # err (no login)
    )
    assert r.summary() == {"total": 4, "ok": 1, "warn": 1, "err": 2, "fatal": []}


def test_template_round_trips():
    text = template_csv()
    r = parse_csv(text)
    # Template contains one example row and two comment lines. Comment lines have
    # `#` in the ip column → invalid IPv4 → err, which is the intended behavior:
    # the user must edit them out.
    assert r.summary()["total"] >= 1
    assert any(row.status == "ok" for row in r.rows)
