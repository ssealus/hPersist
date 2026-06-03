"""Parse PartSurfer's Search.aspx HTML into a structured result.

ASP.NET Web Forms output — element IDs follow ``ctl00_BodyContentPlaceHolder_*``
and are stable across releases. We anchor on:

- ``ctl00_BodyContentPlaceHolder_lblSerialNumber`` / ``lblProductNumber`` /
  ``lblDescription`` / ``lblRoHsStatus`` — product details
- ``ctl00_BodyContentPlaceHolder_gridSpareBOM`` — Spare BOM table

For the "no results" page we look for the error banner text or for the
``comspare_div_empty`` marker.
"""
from __future__ import annotations

from selectolax.parser import HTMLParser, Node

# Visible column headers in PartSurfer's gridSpareBOM, in DOM order. The first
# column ("Add to Cart") is a checkbox we skip. We keep the rest verbatim so
# downstream consumers can render them as-is.
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


def _text(node: Node | None) -> str:
    return node.text(strip=True) if node is not None else ""


def parse(html: str) -> dict:
    """Return ``{"product": {...}, "spare_bom": [{...}], "not_found": bool, "hint": str}``."""
    tree = HTMLParser(html)

    product = {key: _text(tree.css_first(f"#{el_id}")) for key, el_id in _LABEL_IDS.items()}
    product = {k: v for k, v in product.items() if v}

    sbom_table = tree.css_first("#ctl00_BodyContentPlaceHolder_gridSpareBOM")
    rows: list[dict] = []
    if sbom_table is not None:
        for tr in sbom_table.css("tr.RowStyle, tr.AlternatingRowStyle"):
            cells = [_text(td) for td in tr.css("td")]
            # First cell is the "Add to cart" checkbox; data starts at index 1.
            values = cells[1:1 + len(SBOM_COLUMNS)]
            if not any(values):
                continue
            row = dict(zip(SBOM_COLUMNS, values))
            rows.append(row)

    # "No additional information for X found in PartSurfer."
    no_results_banner = tree.css_first("#comspare_div_empty")
    not_found = not product and not rows
    hint = _text(no_results_banner) if no_results_banner is not None else ""

    return {
        "product": product,
        "spare_bom": rows,
        "not_found": not_found,
        "hint": hint,
    }
