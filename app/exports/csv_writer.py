"""CSV writer.

CSV is single-table by definition. We emit the first sheet that matches the
requested layout, or concatenate all three with `## sheet: name` markers if
the caller asked for ``all`` (used by ``Bill of materials`` previews).
"""
from __future__ import annotations

import csv
import io

from app.exports.builder import ExportSheet


def render_csv(sheets: list[ExportSheet], *, only: str | None = None) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    chosen = [s for s in sheets if only is None or s.name.lower().startswith(only.lower())] or sheets
    for i, sheet in enumerate(chosen):
        if i > 0:
            writer.writerow([])
        writer.writerow([f"# sheet: {sheet.name}"])
        writer.writerow(sheet.columns)
        for row in sheet.rows:
            writer.writerow(row)
    return buf.getvalue().encode("utf-8")
