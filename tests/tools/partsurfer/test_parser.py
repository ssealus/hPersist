"""Parser tests against saved PartSurfer HTML — no live network calls."""
from __future__ import annotations

from app.tools.partsurfer.parser import SBOM_COLUMNS, parse


def _load(fixtures_dir, name: str) -> str:
    return (fixtures_dir / "partsurfer" / name).read_text(encoding="utf-8", errors="replace")


def test_parse_found_with_bom_extracts_product_details(fixtures_dir):
    result = parse(_load(fixtures_dir, "found_with_bom.html"))
    assert result["not_found"] is False
    assert result["product"]["serial_number"] == "USE839N0CK"
    assert result["product"]["product_number"] == "491301-001"
    assert "SE1210" in result["product"]["description"]


def test_parse_found_with_bom_extracts_all_rows(fixtures_dir):
    result = parse(_load(fixtures_dir, "found_with_bom.html"))
    assert len(result["spare_bom"]) == 47


def test_parse_each_row_has_all_sbom_columns(fixtures_dir):
    result = parse(_load(fixtures_dir, "found_with_bom.html"))
    for row in result["spare_bom"]:
        assert set(row.keys()) == set(SBOM_COLUMNS)


def test_parse_row_field_values_are_plausible(fixtures_dir):
    result = parse(_load(fixtures_dir, "found_with_bom.html"))
    first = result["spare_bom"][0]
    # All SBOM rows in PartSurfer's gridSpareBOM cross-reference back to the
    # parent product via M_part_Number — sanity check that we mapped the column.
    assert first["m_part_number"] == "491301-001"
    assert first["spare_part_number"]  # non-empty
    assert first["spare_part_description"]


def test_parse_not_found_marks_flag_and_empties_fields(fixtures_dir):
    result = parse(_load(fixtures_dir, "not_found.html"))
    assert result["not_found"] is True
    assert result["product"] == {}
    assert result["spare_bom"] == []


def test_parse_grouped_repeater_layout_for_new_products(fixtures_dir):
    # P52562-B21 (DL380 Gen11) uses the rptRoot/gvProGeneral layout — no
    # gridSpareBOM at all. Parser must walk the per-category repeater and
    # surface a flat row list with the same schema as the legacy path.
    result = parse(_load(fixtures_dir, "product_grouped_bom.html"))
    assert result["not_found"] is False
    assert result["product"].get("product_number") == "P52562-B21"
    assert len(result["spare_bom"]) >= 40, "should harvest ~47 parts across 31 categories"

    # Categories come from KeywordLabel — expect a known set populated.
    cats = {row["category"] for row in result["spare_bom"]}
    assert "PDU" in cats
    assert "Power Supply" in cats

    # Every row keeps the uniform schema and m_part_number defaults to the parent.
    for row in result["spare_bom"]:
        assert set(row.keys()) == set(SBOM_COLUMNS)
        assert row["m_part_number"] == "P52562-B21"


def test_parse_empty_html_is_treated_as_not_found():
    result = parse("<html><body></body></html>")
    assert result["not_found"] is True
    assert result["product"] == {}
    assert result["spare_bom"] == []


def test_sbom_columns_order_matches_partsurfer_grid():
    # Lock the order — if this changes, the API contract changes.
    assert SBOM_COLUMNS == [
        "spare_part_number",
        "spare_part_description",
        "spare_part_description_enhanced",
        "category",
        "most_used",
        "csr",
        "rohs",
        "tech_courier",
        "m_part_number",
    ]
