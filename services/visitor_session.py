#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/visitor_session.py — جلسة الزائر، منفصلةً عن جلسة المنشأة

الزائر يحجز لنفسه ولا يدخل أي تطبيق. لذلك لا يشارك موظفي المنشأة
كوكيَّهم ولا جدولَهم: خلطُهما يعني أن خطأً واحداً في التحقق يمنح
زائراً صلاحيات موظف — وهو أخطر ما في نظامٍ متعدّد المستأجرين.

    كوكي المنشأة   `client_token`   → موظفون · جدول client_sessions
    كوكي الزائر    `visitor_token`  → زوّار   · جدول visitor_sessions

الفصل مادّيٌّ لا اصطلاحي: جلسة زائرٍ لا تُقرأ بدالّة جلسة المنشأة
ولو زُوّرت الكوكي، لأن الجدول الذي تُبحث فيه مختلف.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request

log = logging.getLogger("dheuof.visitor")

COOKIE_NAME = "visitor_token"
SESSION_DAYS = 30

#: نفس قاعدة كوكي المنشأة، لا قاعدةً ثانية.
#
# اخترعتُ هنا افتراضاً مختلفاً (`secure` دائماً ما لم يُطفأ) فرفض
# المتصفّح الكوكي خارج HTTPS ولم تثبت جلسة زائرٍ واحدة — والباب يبدو
# ناجحاً لأن التسجيل يعود ٢٠٠. قاعدتان لنفس القرار تتباعدان دائماً.


def _cookie_secure() -> bool:
    """يُقرأ من `app_core` عند الاستدعاء لا عند الاستيراد: القراءة عند
    الاستيراد تُثبّت القيمة قبل تحميل الإعدادات."""
    from app_core import _COOKIE_SECURE

    return _COOKIE_SECURE


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        return None
    return db


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ── إنشاء ───────────────────────────────────────────────────────
def create(request: Request, visitor_id: int, client_id: str) -> str | None:
    """
    يُنشئ جلسة زائر ويعيد رمزها.

    `client_id` مخزَّن في الجلسة لا في الطلب: الزائر يحجز في منشأةٍ
    بعينها، ولو قُرئ المُعرّف من جسم الطلب لاستطاع الحجز — والاطّلاع —
    في منشأةٍ أخرى بتغيير رقم.
    """
    db = _db(request)
    if not db:
        return None
    token = secrets.token_urlsafe(32)
    try:
        db.execute(
            """INSERT INTO visitor_sessions (token, visitor_id, client_id, expires_at)
               VALUES (%s, %s, %s, %s)""",
            (token, visitor_id, client_id, _now() + timedelta(days=SESSION_DAYS)),
        )
    except Exception as exc:
        log.error("تعذّر إنشاء جلسة زائر: %s", exc, exc_info=True)
        return None
    return token


def attach_cookie(response, token: str) -> None:
    """يضع الكوكي على الردّ. HttpOnly — لا يراها الجافاسكربت."""
    response.set_cookie(
        COOKIE_NAME, token,
        httponly=True, samesite="lax", secure=_cookie_secure(),
        max_age=86400 * SESSION_DAYS,
    )


# ── قراءة ───────────────────────────────────────────────────────
def session_from_request(request: Request) -> dict | None:
    """
    جلسة الزائر من الكوكي، أو `None`.

    الجلسة المنتهية تُحذف ولا تُعاد: تركُها يعني أن زائراً يعود بعد
    شهورٍ فيجد جلسته حيّة.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    db = _db(request)
    if not db:
        return None
    row = db.execute(
        """SELECT s.token, s.visitor_id, s.client_id, s.expires_at,
                  v.full_name, v.phone, v.email
           FROM visitor_sessions s
           JOIN visitors v ON v.id = s.visitor_id
           WHERE s.token = %s""",
        (token,), fetch="one",
    )
    if not row:
        return None
    row = dict(row)
    expires = row.get("expires_at")
    if expires and expires <= _now():
        revoke(request, token)
        return None
    return {
        "kind": "visitor",          # لا `role`: لا يشبه موظفاً في شيء
        "visitor_id": row["visitor_id"],
        "client_id": row["client_id"],
        "full_name": row.get("full_name"),
        "phone": row.get("phone"),
        "email": row.get("email"),
    }


# ── حارس بوابة الحجز ────────────────────────────────────────────
def require_visitor(request: Request) -> dict:
    """
    حارس الزائر — يعيش هنا مع تطبيق الحجز، لا بين حرّاس المنشأة.

    الزائر ليس مرتبةً من مراتب PMS ولا مساراً من مساراته الأربعة؛ هو
    جهة تطبيق الحجز وحدها. لذلك حارسُه في طبقة الحجز مع جلسته المنفصلة
    (كوكي `visitor_token` وجدول `visitor_sessions`)، لا في `db/access.py`
    حيث خلطُه بحرّاس المنشأة يوحي بأنه مرتبةٌ داخلية.
    """
    session = session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="سجّل دخولك لبوابة الحجز")
    return session


def revoke(request: Request, token: str | None) -> None:
    db = _db(request)
    if not db or not token:
        return
    try:
        db.execute("DELETE FROM visitor_sessions WHERE token=%s", (token,))
    except Exception as exc:
        log.warning("تعذّر إبطال جلسة الزائر: %s", exc)
