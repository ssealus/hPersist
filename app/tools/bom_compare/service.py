"""BOM Compare orchestrator — load two inventories, hand off to the differ."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Inventory
from app.tools.bom_compare.differ import diff_inventories


def compare(session: Session, *, inventory_a_id: str, inventory_b_id: str) -> dict:
    if inventory_a_id == inventory_b_id:
        raise ValueError("pick two different inventories")
    a = session.get(Inventory, inventory_a_id)
    if a is None:
        raise ValueError(f"inventory_a not found: {inventory_a_id}")
    b = session.get(Inventory, inventory_b_id)
    if b is None:
        raise ValueError(f"inventory_b not found: {inventory_b_id}")
    return diff_inventories(a, b)
