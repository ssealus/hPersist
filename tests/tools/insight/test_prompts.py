"""Prompts — message shape per mode, validation errors."""
from __future__ import annotations

import pytest

from app.tools.insight.prompts import (
    REPORT_CHOICES,
    REPORT_TEMPLATES,
    SYSTEM,
    build_messages,
)


def test_build_messages_summary_mode_returns_two_messages():
    msgs = build_messages("summary", payload_json="{}")
    assert len(msgs) == 2
    assert msgs[0] == {"role": "system", "content": SYSTEM}
    assert msgs[1]["role"] == "user"
    assert "{}" in msgs[1]["content"]


def test_build_messages_analytics_requires_question():
    with pytest.raises(ValueError, match="analytics mode requires a question"):
        build_messages("analytics", payload_json="{}")
    with pytest.raises(ValueError):
        build_messages("analytics", payload_json="{}", question="   ")


def test_build_messages_analytics_includes_question_verbatim():
    msgs = build_messages("analytics", payload_json="{}", question="which hosts are off?")
    assert "which hosts are off?" in msgs[1]["content"]


def test_build_messages_reports_requires_known_template():
    with pytest.raises(ValueError, match="unknown report template"):
        build_messages("reports", payload_json="{}", template="bogus")


def test_build_messages_reports_emits_template_body():
    msgs = build_messages("reports", payload_json="{}", template="procurement")
    # procurement template should mention some characteristic word
    assert "procurement" in msgs[1]["content"].lower()


def test_build_messages_unknown_mode_raises():
    with pytest.raises(ValueError, match="unknown mode"):
        build_messages("nonsense", payload_json="{}")


def test_report_choices_matches_template_keys():
    # REPORT_CHOICES must always equal REPORT_TEMPLATES.keys() — keep in sync.
    assert set(REPORT_CHOICES) == set(REPORT_TEMPLATES.keys())
