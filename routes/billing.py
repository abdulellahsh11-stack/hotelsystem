#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/billing.py — بوابة الفوترة للمنشأة (البند: إضافة بوابة الفوترة).

- GET  /api/billing/portal    — لوحةٌ موجزة: حالة الاشتراك، الخطة، وضع
  ميسر (حيّ/اختبار)، وتعليمات الدفع.
- GET  /api/billing/invoices  — دفعات المنشأة (تُقرأ من payments، معزولةً
  بـclient_id).
- POST /api/billing/checkout  — يبدأ دفعة تجديدٍ في ميسر ويعيد معرّفها كي
  تُكمَّل من الواجهة. المبلغ يُحوَّل للوحدة الصغرى عبر billing_money.

هوية المنشأة من الجلسة دائماً. لا نثق بمبلغٍ من الواجهة إلا ضمن أسعار
الخطط المعروفة (لا مبلغ حرّ).
"""
from fastapi import APIRouter, Depends, Request

from app_core import require_client
from db.access import require_manager
from services import billing_money, moyasar_gateway, subscription

router = APIRouter()

# أسعار الخطط الشهرية (بالريال) — مصدرٌ خادميّ، لا مبلغ من الواجهة.
PLAN_PRICES = {"starter": 199.0, "business": 399.0, "enterprise": 799.0}


@router.get("/api/billing/portal")
async def billing_portal(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    status = subscription.evaluate(client)
    return {"success": True, "data": {
        "status": status,
        "plan": client.get("plan", "trial"),
        "prices": PLAN_PRICES,
        "gateway": {"test_mode": moyasar_gateway.is_test_mode(),
                    "configured": bool(moyasar_gateway.api_key())},
        "payment": subscription.payment_instructions(client),
    }}


@router.get("/api/billing/invoices")
async def billing_invoices(request: Request, session=Depends(require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    rows = []
    if getattr(db, "use_postgres", False):
        rows = db.execute(
            """SELECT amount, currency, method, reference, created_at
               FROM payments WHERE client_id=%s
               ORDER BY created_at DESC LIMIT 100""",
            (cid,), fetch="all") or []
        rows = [dict(r) for r in rows]
    return {"success": True, "data": rows}


@router.post("/api/billing/checkout")
async def billing_checkout(request: Request, session=Depends(require_manager)):
    """يبدأ دفعة تجديدٍ لخطةٍ معروفة. المصدر (بطاقة/إلخ) من الواجهة، والمبلغ
    من أسعارنا لا منها."""
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    plan = str(data.get("plan", "")).strip()
    if plan not in PLAN_PRICES:
        return {"success": False, "error": "خطة غير معروفة"}
    if not moyasar_gateway.api_key():
        return {"success": False, "error": "بوابة الدفع غير مهيّأة"}
    client = store.get_client(cid) or {}
    currency = billing_money.normalize_currency(data.get("currency", "SAR"))
    total = billing_money.add_vat(PLAN_PRICES[plan])["total"]
    amount_minor = billing_money.to_minor(total, currency)
    source = data.get("source") or {"type": "creditcard"}
    result = moyasar_gateway.create_payment(
        amount_minor, currency, f"اشتراك {plan} — {client.get('name', cid)}",
        cid, source, reference=f"sub:{plan}",
        callback_url=data.get("callback_url"))
    if not result.get("ok"):
        return {"success": False, "error": "تعذّر بدء الدفع", "detail": result.get("error")}
    return {"success": True, "data": {"payment_id": result["payment_id"],
            "status": result["status"], "test_mode": result["test_mode"]}}
