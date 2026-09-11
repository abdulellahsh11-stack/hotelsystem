#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/moyasar_webhook.py — نقطة استقبال ويب هوك ميسر.

عامّة (تناديها البوابة لا مستخدم) لكنها **لا تثق** بشيء: التوقيع يُتحقّق
على الجسم الخام قبل أيّ عمل. توقيعٌ خاطئ يعود 401 ولا يُعالَج. المنشأة
تأتي من metadata الموقَّعة، لا من الجلسة (لا جلسة هنا).

نُعيد 200 حتى للحدث المكرَّر كي لا تعيد ميسر الإرسال بلا داعٍ؛ ونعيد 401
وحدها للتوقيع الخاطئ.
"""
import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services import moyasar

router = APIRouter()


@router.post("/api/webhooks/moyasar")
async def moyasar_webhook(request: Request):
    raw = await request.body()
    signature = (request.headers.get("x-moyasar-signature")
                 or request.headers.get("x-signature") or "")
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        payload = {}
    store = request.app.state.store
    db = request.app.state.db
    # تدفّقٌ آمن: يحجز ثم يطبّق ثم يؤكّد، ويحرّر الحجز عند الفشل.
    result = moyasar.handle_webhook(db, store, raw, signature, payload)
    if not result.get("ok"):
        reason = result.get("reason", "unauthorized")
        # فشل التطبيق قابلٌ للإعادة → 500 كي تعيد ميسر الإرسال؛ التوقيع → 401.
        code = 500 if result.get("retry") else 401
        return JSONResponse(status_code=code, content={"success": False, "error": reason})
    return {"success": True, "duplicate": result.get("duplicate", False),
            "action": result.get("action"), "applied": result.get("applied")}
