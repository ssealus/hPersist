"""Parse PartSurfer's Search.aspx HTML into a structured result.

ASP.NET Web Forms output. PartSurfer uses TWO different SBOM layouts depending
on the product:

1. Legacy single-table layout (``gridSpareBOM``): one flat ``<table>`` with
   header row + ``RowStyle`` / ``AlternatingRowStyle`` data rows. Used by older
   product numbers (e.g. SE1210 / 491301-001).

2. Grouped repeater layout (``rptRoot``): a repeater of category groups, each
   with a ``KeywordLabel`` (PDU / Cable / Drive / …) and an inner GridView
   (``gvProGeneral``) holding the rows for that category. Used by newer
   product numbers (DL380 Gen11 / P52562-B21 etc.).

We harvest both and return a single flat list of rows with a uniform schema —
the UI doesn't have to care which layout the upstream sent.
"""
from __future__ import annotations

from selectolax.parser import HTMLParser, Node

# Uniform per-row schema. Both legacy and grouped layouts populate the same
# keys; missing fields stay as empty strings so the UI never sees None.
SBOM_COLUMNS = [
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

_LABEL_IDS = {
    "serial_number":  "ctl00_BodyContentPlaceHolder_lblSerialNumber",
    "product_number": "ctl00_BodyContentPlaceHolder_lblProductNumber",
    "description":    "ctl00_BodyContentPlaceHolder_lblDescription",
    "rohs_status":    "ctl00_BodyContentPlaceHolder_lblRoHsStatus",
}

# Map per-row label-ID suffix (the part after ``gvProGeneral_ctlN_``) to our
# uniform column name. The grouped layout doesn't carry an "Enhanced" or
# explicit "M_part_Number" column; those stay blank or come from the parent.
_GROUPED_FIELD_MAP = {
    "lnkPartno":   "spare_part_number",
    "lbldesc":     "spare_part_description",
    "lblcsr":      "csr",
    "lblrohs":     "rohs",
    "lbltc":       "tech_courier",
    "lblMostUsed": "most_used",
}


def _text(node: Node | None) -> str:
    return node.text(strip=True) if node is not None else ""


def _empty_row() -> dict:
    return dict.fromkeys(SBOM_COLUMNS, "")


def _parse_legacy_table(tree: HTMLParser) -> list[dict]:
    """gridSpareBOM — flat table, one row per part."""
    sbom_table = tree.css_first("#ctl00_BodyContentPlaceHolder_gridSpareBOM")
    if sbom_table is None:
        return []
    rows: list[dict] = []
    for tr in sbom_table.css("tr.RowStyle, tr.AlternatingRowStyle"):
        cells = [_text(td) for td in tr.css("td")]
        # First cell is the "Add to cart" checkbox; data starts at index 1.
        values = cells[1:1 + len(SBOM_COLUMNS)]
        if not any(values):
            continue
        rows.append(dict(zip(SBOM_COLUMNS, values, strict=False)))
    return rows


def _parse_grouped_repeater(tree: HTMLParser, parent_pn: str) -> list[dict]:
    """rptRoot — category groups (PDU, Drive, …) with per-category GridViews.

    ASP.NET's GridView doesn't emit an outer ID on the grid table itself; only
    the per-cell spans/links inside carry IDs like ``rptRoot_ctlN_gvProGeneral_ctlM_*``.
    So we walk those cell IDs, bucket them by (N, M), and reassemble rows.
    """
    # First pass: category per group N (from the KeywordLabel span).
    categories: dict[str, str] = {}
    for label in tree.css('[id*="_KeywordLabel"]'):
        label_id = label.attributes.get("id") or ""
        if "_rptRoot_ctl" not in label_id:
            continue
        # group index N — between "rptRoot_ctl" and "_KeywordLabel"
        try:
            n = label_id.split("_rptRoot_ctl", 1)[1].split("_", 1)[0]
        except IndexError:
            continue
        categories[n] = label.text(strip=True)

    # Second pass: bucket every cell with a {N, M, suffix} ID into rows.
    buckets: dict[tuple[str, str], dict] = {}
    for el in tree.css("[id]"):
        el_id = el.attributes.get("id") or ""
        if "_rptRoot_ctl" not in el_id or "_gvProGeneral_ctl" not in el_id:
            continue
        # ID shape: …rptRoot_ctl{N}_gvProGeneral_ctl{M}_{suffix}
        head, _, suffix = el_id.rpartition("_")
        if not suffix:
            continue
        # Verify the suffix is one we care about — saves work + cleanly skips
        # the boilerplate `_aid` cell and unrelated children.
        column = _GROUPED_FIELD_MAP.get(suffix)
        if column is None:
            continue
        # Extract N and M.
        try:
            after_rpt = el_id.split("_rptRoot_ctl", 1)[1]
            n, after_n = after_rpt.split("_gvProGeneral_ctl", 1)
            m = after_n.split("_", 1)[0]
        except (IndexError, ValueError):
            continue

        key = (n, m)
        if key not in buckets:
            row = _empty_row()
            row["category"] = categories.get(n, "")
            row["m_part_number"] = parent_pn
            buckets[key] = row
        val = el.text(strip=True)
        if val:
            buckets[key][column] = val

    rows = [r for r in buckets.values() if r["spare_part_number"]]
    return rows


def parse(html: str) -> dict:
    """Return ``{"product": {...}, "spare_bom": [{...}], "not_found": bool, "hint": str}``."""
    tree = HTMLParser(html)

    product = {key: _text(tree.css_first(f"#{el_id}")) for key, el_id in _LABEL_IDS.items()}
    product = {k: v for k, v in product.items() if v}

    rows = _parse_legacy_table(tree)
    if not rows:
        rows = _parse_grouped_repeater(tree, parent_pn=product.get("product_number", ""))

    no_results_banner = tree.css_first("#comspare_div_empty")
    not_found = not product and not rows
    hint = _text(no_results_banner) if no_results_banner is not None else ""

    return {
        "product": product,
        "spare_bom": rows,
        "not_found": not_found,
        "hint": hint,
    }
