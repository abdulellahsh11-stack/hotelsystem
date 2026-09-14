#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/stock.py — مخزون الاستهلاك لكل نزيل (تعبئة · إعداد النقص · غسيل).

المالك أو المدير (require_manager) يُعبّئ الكميّات ويحدّد النقص لكل نزيل ونوع
الصنف. العرض للجميع المخوَّلين. الاستهلاك التلقائي يقع عند تسجيل الدخول.

    GET  /api/stock/items                    الأصناف بكميّاتها (نظيف/متّسخ · النقص)
    POST /api/stock/items/{id}/config        ضبط النقص لكل نزيل ونوع الصنف
    POST /api/stock/items/{id}/refill        تعبئة كميّة
    POST /api/stock/items/{id}/laundry-return إرجاع من الغسيل (متّسخ→نظيف)
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app_core import require_client
from db.access import require_manager
from services import stock_consumption as stock

router = APIRouter(prefix="/api/stock", tags=["Stock"])

KINDS = {"consumable", "reusable"}


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="الخدمة غير متاحة مؤقتاً")
    return db


@router.get("/items")
async def list_items(request: Request, session=Depends(require_client)):
    db = _db(request)
    rows = db.execute(
        """SELECT id, name, unit, item_kind, per_guest, quantity, dirty_quantity,
                  reorder_level
             FROM warehouse_items WHERE client_id=%s ORDER BY name""",
        (session["client_id"],), fetch="all") or []
    data = []
    for r in rows:
        d = dict(r)
        for k in ("per_guest", "quantity", "dirty_quantity", "reorder_level"):
            d[k] = float(d.get(k) or 0)
        d["low"] = d["quantity"] <= d["reorder_level"]
        data.append(d)
    return {"success": True, "data": data}


@router.post("/items/{item_id}/config")
async def config_item(item_id: int, request: Request, session=Depends(require_manager)):
    """يحدّد المدير/المالك النقص لكل نزيل ونوع الصنف (مستهلَك/قابل لإعادة)."""
    data = await request.json()
    kind = str(data.get("item_kind") or "consumable").strip().lower()
    if kind not in KINDS:
        raise HTTPException(status_code=400, detail="نوع صنفٍ غير معروف")
    try:
        per_guest = round(float(data.get("per_guest") or 0), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="معدّل النقص غير صحيح") from None
    if per_guest < 0:
        raise HTTPException(status_code=400, detail="معدّل النقص لا يكون سالباً")
    db = _db(request)
    row = db.execute(
        """UPDATE warehouse_items SET item_kind=%s, per_guest=%s, updated_at=NOW()
           WHERE id=%s AND client_id=%s RETURNING id""",
        (kind, per_guest, item_id, session["client_id"]), fetch="one")
    if not row:
        raise HTTPException(status_code=404, detail="الصنف غير موجود")
    return {"success": True, "data": {"id": item_id, "item_kind": kind,
            "per_guest": per_guest}}


@router.post("/items/{item_id}/refill")
async def refill_item(item_id: int, request: Request, session=Depends(require_manager)):
    """يُعبّئ المالك/المدير كميّة الصنف (تُضاف إلى النظيف)."""
    data = await request.json()
    try:
        amount = round(float(data.get("amount") or 0), 2)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="كميّة غير صحيحة") from None
    if amount <= 0:
        raise HTTPException(status_code=400, detail="الكميّة يجب أن تكون موجبة")
    db = _db(request)
    cid = session["client_id"]
    row = db.execute(
        """UPDATE warehouse_items SET quantity=quantity+%s, updated_at=NOW()
           WHERE id=%s AND client_id=%s RETURNING quantity""",
        (amount, item_id, cid), fetch="one")
    if not row:
        raise HTTPException(status_code=404, detail="الصنف غير موجود")
    db.execute(
        """INSERT INTO warehouse_movements
               (item_id, client_id, movement_type, quantity, notes, created_by)
           VALUES (%s,%s,'in',%s,'تعبئة مخزون',%s)""",
        (item_id, cid, amount, "manager"))
    return {"success": True, "data": {"id": item_id,
            "quantity": float(dict(row)["quantity"])}}


@router.post("/items/{item_id}/laundry-return")
async def laundry_return(item_id: int, request: Request, session=Depends(require_manager)):
    """يُعيد كميّةً من المتّسخ إلى النظيف بعد الغسيل."""
    data = await request.json()
    res = stock.return_from_laundry(_db(request), session["client_id"],
                                    item_id, data.get("amount"))
    if res is None:
        raise HTTPException(status_code=400,
                            detail="تعذّر الإرجاع — صنفٌ غير قابلٍ لإعادة الاستخدام أو كميّة غير صحيحة")
    return {"success": True, "data": {"id": item_id, **res}}
