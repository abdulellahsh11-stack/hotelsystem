#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/integrations.py — إعداد اعتمادات التكاملات تحت تصرّف المشترك.

كل منشأةٍ تربط اعتمادها الخاص لكل خدمة (دفع الضيوف · قنوات OTA · الزكاة ·
شموس · NTMP) وتراه مقنّعاً وتفصله. **لا يخرج السرّ خاماً أبداً**؛ العرض قناعٌ
وحالة فقط. هوية المنشأة من الجلسة دائماً.
"""
from fastapi import APIRouter, Depends, Request

from db.access import require_manager
from services import integration_credentials as vault

router = APIRouter()

# الخدمات المسموح ربطها — قائمة مضبوطة لا نصّ حر.
ALLOWED = {"moyasar_guest", "booking", "almosafer", "agoda", "expedia",
           "airbnb", "zatca", "shomoos", "ntmp"}


@router.get("/api/integrations")
async def list_integrations(request: Request, session=Depends(require_manager)):
    """حالة كل التكاملات لهذه المنشأة — مقنّعة، بلا أسرار."""
    db = request.app.state.db
    return {"success": True, "data": vault.status(db, session["client_id"])}


@router.post("/api/integrations/{service}")
async def set_integration(service: str, request: Request,
                          session=Depends(require_manager)):
    """يرفع المشترك اعتماد خدمةٍ (يُخزَّن مشفّراً). يعيد الحالة المقنّعة."""
    if service not in ALLOWED:
        return {"success": False, "error": "خدمة غير مدعومة"}
    body = await request.json()
    secret = body.get("credentials") if isinstance(body.get("credentials"), dict) else body
    result = vault.save(request.app.state.db, session["client_id"], service, secret)
    if not result.get("persisted") and result.get("error"):
        return {"success": False, "error": result["error"], "data": result}
    return {"success": True, "data": result}


@router.delete("/api/integrations/{service}")
async def delete_integration(service: str, request: Request,
                             session=Depends(require_manager)):
    """يفصل المشترك اعتماد خدمة."""
    vault.delete(request.app.state.db, session["client_id"], service)
    return {"success": True}
