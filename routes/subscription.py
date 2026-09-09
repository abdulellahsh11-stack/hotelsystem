#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/subscription.py — حالة الاشتراك ورسالة الدفع (البند ٣).

- GET  /api/subscription/status         — حالةٌ للمنشأة: كم بقي، تنبيهٌ قبل
  القفل بـ٢٤ ساعة، هل قُفل، وتعليمات الدفع.
- POST /api/subscription/payment-message — يكتب مالك/مدير المنشأة رسالة
  التحويل البنكي أو رابط ميسر، فتظهر عند التجديد.

هوية المنشأة من الجلسة دائماً، والكتابة تحفظ بقيّة الإعدادات كما هي
(لا تلمس settings._account).
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app_core import require_client
from db.access import require_manager
from services import subscription

router = APIRouter()


def require_module(module: str):
    """حمايةٌ خادميّة لوحدةٍ تحتاج خطةً أعلى — قرارٌ لا يُترك للواجهة.

    تُستعمل: `Depends(require_module("channels"))`. تمنع (٤٠٢/٤٠٣) إن كانت
    خطة المنشأة أدنى من الوحدة أو اشتراكها مقفلاً.
    """
    def _guard(request: Request, session=Depends(require_client)) -> dict:
        client = request.app.state.store.get_client(session["client_id"]) or {}
        if not subscription.is_accessible(client):
            raise HTTPException(status_code=402,
                                detail="اشتراك المنشأة منتهٍ — جدّد للمتابعة")
        if not subscription.can_use(client, module):
            raise HTTPException(status_code=403,
                                detail="هذه الميزة تتطلّب ترقية الباقة")
        return session
    return _guard


@router.get("/api/subscription/status")
async def subscription_status(request: Request, session=Depends(require_client)):
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    data = subscription.evaluate(client)
    data["plan"] = client.get("plan", "trial")
    data["payment"] = subscription.payment_instructions(client)
    return {"success": True, "data": data}


@router.post("/api/subscription/payment-message")
async def set_payment_message(request: Request, session=Depends(require_manager)):
    """يخصّص رسالة/تعليمات الدفع (تحويل بنكي أو رابط ميسر) — للمالك أو المدير."""
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    settings = dict(client.get("settings") or {})
    settings["subscription_payment"] = subscription.sanitize_payment(data)
    client["settings"] = settings
    store.save_client(client)
    return {"success": True, "data": subscription.payment_instructions(client)}


@router.post("/api/subscription/change-plan")
async def change_plan(request: Request, session=Depends(require_manager)):
    """ترقية/هبوط الباقة — للمالك أو المدير. التحصيل التناسبي عند البوابة."""
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    result = subscription.change_plan(client, str(data.get("plan", "")))
    client["plan"] = result["plan"]
    store.save_client(client)
    return {"success": True, "data": result}


@router.post("/api/subscription/cancel")
async def cancel_subscription(request: Request, session=Depends(require_manager)):
    """إلغاءٌ يعمل: يوقف التجديد ويُبقي الوصول حتى نهاية المدّة المدفوعة."""
    store = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    client.update(subscription.cancel(client))
    store.save_client(client)
    return {"success": True, "data": subscription.evaluate(client)}
