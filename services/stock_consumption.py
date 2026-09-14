#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/stock_consumption.py — استهلاك المخزون التلقائي لكل نزيل.

المالك أو المدير أو المسؤول (حسب الصلاحية) يُعبّئ الكميّات ويحدّد **النقص
لكل نزيل** (`per_guest`) ونوع الصنف:

- **مستهلَك** (شامبو · ماء): يَنقص نهائياً عند إضافة نزيل.
  ٥٠٠ شامبو، نزيلٌ واحد بمعدّل ١ → ٤٩٩.
- **قابل لإعادة الاستخدام** (فوط): لا يَنقص بل ينتقل من **النظيف إلى المتّسخ**،
  والمجموع محفوظ. ٣٠٠ فوطة، نزيلٌ واحد بمعدّل ١ → نظيفة ٢٩٩ ومتّسخة ١.
  نزيلٌ ومرافقٌ (شخصان) بمعدّل ١ → نظيفة ٢٩٨ ومتّسخة ٢.

النقص = `per_guest × عدد الأشخاص` (النزيل + مرافقوه). المنطق الحسابي خالصٌ
يُختبَر بالكسر؛ لمس القاعدة معزولٌ يحرس `use_postgres` بلا هبوطٍ تحت الصفر.
"""
from __future__ import annotations

CONSUMABLE = "consumable"
REUSABLE = "reusable"


def _pg(db) -> bool:
    return bool(getattr(db, "use_postgres", False))


def plan(items, persons) -> list[dict]:
    """يحسب النقص لكل صنفٍ لعددٍ من الأشخاص. خالصٌ.

    persons = النزيل + مرافقوه (بحدٍّ أدنى ١). الأصناف بلا `per_guest` تُتجاهَل.
    """
    p = max(1, int(persons or 1))
    out: list[dict] = []
    for it in items or []:
        try:
            rate = float(it.get("per_guest") or 0)
        except (TypeError, ValueError):
            continue
        amount = round(rate * p, 2)
        if amount > 0:
            out.append({
                "id": it.get("id"),
                "name": it.get("name"),
                "kind": (it.get("item_kind") or CONSUMABLE),
                "amount": amount,
            })
    return out


def consume_for_stay(db, client_id: str, persons: int,
                     booking_id=None, actor: str = "reception") -> dict:
    """يطبّق الاستهلاك على مخزون المنشأة عند إضافة نزيل.

    مستهلَك → نقصٌ نهائي (`quantity`, لا يهبط تحت الصفر). قابل لإعادة الاستخدام
    → نظيف يَنقص والمتّسخ يزيد بنفس القدر (المجموع محفوظ). يسجّل حركةً لكلٍّ.
    في التطوير (بلا PostgreSQL) يعود فارغاً دون سقوطٍ صامت.
    """
    if not _pg(db):
        return {}
    items = db.execute(
        """SELECT id, name, item_kind, per_guest, quantity, dirty_quantity
             FROM warehouse_items
            WHERE client_id=%s AND per_guest > 0""",
        (client_id,), fetch="all") or []
    result: dict = {}
    for planned in plan([dict(r) for r in items], persons):
        iid, amt, kind = planned["id"], planned["amount"], planned["kind"]
        if kind == REUSABLE:
            # النظيف يَنقص (لا تحت الصفر)، والمتّسخ يزيد بما نُقص فعلاً.
            row = db.execute(
                """UPDATE warehouse_items
                     SET quantity = GREATEST(quantity - %s, 0),
                         dirty_quantity = dirty_quantity + LEAST(quantity, %s),
                         updated_at = NOW()
                   WHERE id=%s AND client_id=%s
                   RETURNING quantity, dirty_quantity""",
                (amt, amt, iid, client_id), fetch="one")
            move = "soiled"
        else:
            row = db.execute(
                """UPDATE warehouse_items
                     SET quantity = GREATEST(quantity - %s, 0), updated_at = NOW()
                   WHERE id=%s AND client_id=%s
                   RETURNING quantity, dirty_quantity""",
                (amt, iid, client_id), fetch="one")
            move = "out"
        if not row:
            continue
        r = dict(row)
        db.execute(
            """INSERT INTO warehouse_movements
                   (item_id, client_id, movement_type, quantity, booking_id, notes, created_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (iid, client_id, move, amt, booking_id,
             f"استهلاك {planned['name']} لعددٍ من الأشخاص", actor))
        result[planned["name"]] = {
            "kind": kind, "amount": amt,
            "clean": float(r.get("quantity") or 0),
            "dirty": float(r.get("dirty_quantity") or 0),
        }
    return result


def return_from_laundry(db, client_id: str, item_id, amount, actor: str = "housekeeping") -> dict | None:
    """يُعيد كميّةً من المتّسخ إلى النظيف بعد الغسيل (المتّسخ→النظيف).

    لا يُعيد أكثر من المتّسخ المتوفّر. يسجّل حركة `laundry_in`.
    """
    if not _pg(db):
        return None
    try:
        amt = round(float(amount or 0), 2)
    except (TypeError, ValueError):
        return None
    if amt <= 0:
        return None
    row = db.execute(
        """UPDATE warehouse_items
             SET dirty_quantity = GREATEST(dirty_quantity - %s, 0),
                 quantity = quantity + LEAST(dirty_quantity, %s),
                 updated_at = NOW()
           WHERE id=%s AND client_id=%s AND item_kind='reusable'
           RETURNING quantity, dirty_quantity""",
        (amt, amt, item_id, client_id), fetch="one")
    if not row:
        return None
    db.execute(
        """INSERT INTO warehouse_movements
               (item_id, client_id, movement_type, quantity, notes, created_by)
           VALUES (%s,%s,'laundry_in',%s,%s,%s)""",
        (item_id, client_id, amt, "إرجاع من الغسيل (متّسخ→نظيف)", actor))
    r = dict(row)
    return {"clean": float(r.get("quantity") or 0), "dirty": float(r.get("dirty_quantity") or 0)}
