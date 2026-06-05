"""Export endpoint — produces XLSX, CSV or JSON bytes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.schemas import ExportRequest
from app.db import get_session
from app.exports.builder import ExportOptions, build_sheets
from app.exports.csv_writer import render_csv
from app.exports.xlsx import render_xlsx
from app.models import Inventory

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post("")
def export(req: ExportRequest, session: Session = Depends(get_session)) -> Response:
    inventories = [session.get(Inventory, i) for i in req.inventory_ids]
    inventories = [i for i in inventories if i is not None]
    if not inventories:
        raise HTTPException(404, "no inventories found for those ids")

    options = ExportOptions.from_dict({
        "layout": req.layout,
        "groups": req.groups,
        "include_columns": req.include_columns,
        "anonymize": req.anonymize,
        "inventory_ids": req.inventory_ids,
    })
    sheets = build_sheets(session, inventories, options)
    filename_base = "_".join(i.name.replace(" ", "-")[:24] for i in inventories[:2]) or "hpersist-export"

    if req.format == "xlsx":
        data = render_xlsx(sheets, title=filename_base)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.xlsx"'},
        )
    if req.format == "csv":
        data = render_csv(sheets)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.csv"'},
        )
    if req.format == "json":
        body = {
            "inventories": [{"id": i.id, "name": i.name} for i in inventories],
            "sheets": [{"name": s.name, "columns": s.columns, "rows": s.rows} for s in sheets],
        }
        return Response(
            content=json.dumps(body, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename_base}.json"'},
        )
    raise HTTPException(400, "unsupported format")
