#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/visitors.py — بوابة الزوّار: حجزٌ لأنفسهم لا غير

تطبيق الحجز، لا مساراً من مسارات PMS الأربعة. ما يستطيعه الزائر:

    ✅ يُنشئ حساباً بجواله واسمه
    ✅ يرى أنواع الغرف وأسعارها في منشأةٍ واحدة
    ✅ يطلب حجزاً **لنفسه** · يرى طلباته · يلغيها قبل التأكيد

وما لا يستطيعه — وكلٌّ منها ممنوعٌ على الخادم لا بإخفاء زرّ:

    ❌ يدخل أي تطبيق تشغيل           `require_staff` يرفض جلسته
    ❌ يحجز باسم ضيفٍ آخر            لا مسار هنا يقبل اسم غيره
    ❌ يرى نزيلاً أو حجزاً ليس له     كل استعلامٍ مُقيَّد بـ visitor_id
    ❌ يرى منشأةً غير منشأته          `client_id` من الجلسة لا الطلب

**الطلب ليس حجزاً.** يصل بحالة `pending` وينتظر تأكيد المنشأة، ثم
يُحوّله موظفٌ مخوَّل إلى حجزٍ حقيقي ويأخذ الهوية عند الوصول.
"""
from __future__ import annotations

import logging
import secrets
from datetime import date

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from db.connection import count_of
from services import visitor_session
from services.visitor_session import require_visitor

router = APIRouter(prefix="/api/visit", tags=["Visitors"])
log = logging.getLogger("dheuof.visitors")

MIN_PASSWORD = 8
MAX_NIGHTS = 90
MAX_PENDING = 5          # حدٌّ يمنع إغراق المنشأة بطلباتٍ وهمية


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="الخدمة غير متاحة مؤقتاً")
    return db


def _norm_phone(raw: str) -> str:
    """يوحّد الجوال: أرقام لاتينية بلا فراغاتٍ ولا شرطات."""
    table = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    return "".join(c for c in str(raw or "").translate(table) if c.isdigit() or c == "+")


# ── الحساب ──────────────────────────────────────────────────────
@router.post("/register")
async def visitor_register(request: Request):
    """
    حساب زائرٍ جديد في منشأةٍ بعينها.

    `client_id` يأتي من الطلب هنا **وحدها** — لأن الزائر يختار المنشأة
    التي يحجز فيها قبل أن تكون له جلسة. وبعد الدخول تأتي من الجلسة
    دائماً.
    """
    from app_core import _make_password

    data = await request.json()
    db = _db(request)

    client_id = str(data.get("client_id") or "").strip()
    full_name = str(data.get("full_name") or "").strip()
    phone = _norm_phone(data.get("phone"))
    email = str(data.get("email") or "").strip() or None
    password = str(data.get("password") or "")

    if not client_id or not db.execute(
        "SELECT id FROM clients WHERE id=%s", (client_id,), fetch="one"
    ):
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    if not full_name:
        raise HTTPException(status_code=400, detail="الاسم مطلوب")
    if len(phone) < 9:
        raise HTTPException(status_code=400, detail="رقم جوال غير صحيح")
    if len(password) < MIN_PASSWORD:
        raise HTTPException(
            status_code=400, detail=f"كلمة المرور {MIN_PASSWORD} محارف على الأقل"
        )

    pass_hash, pass_salt = _make_password(password)
    try:
        row = db.execute(
            """INSERT INTO visitors (client_id, full_name, phone, email, pass_hash, pass_salt)
               VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
            (client_id, full_name, phone, email, pass_hash, pass_salt), fetch="one",
        )
    except Exception as exc:
        if "unique" in str(exc).lower() or "duplicate" in str(exc).lower():
            raise HTTPException(
                status_code=409, detail="هذا الجوال مسجَّل — سجّل الدخول"
            ) from exc
        log.error("فشل تسجيل زائر: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="تعذّر إنشاء الحساب") from exc

    visitor_id = dict(row)["id"]
    token = visitor_session.create(request, visitor_id, client_id)
    response = JSONResponse({"success": True, "data": {"full_name": full_name}})
    if token:
        visitor_session.attach_cookie(response, token)
    return response


@router.post("/login")
async def visitor_login(request: Request):
    """
    دخول الزائر.

    رسالة الفشل موحَّدة لكل سبب: اختلافُها يكشف أي جوالٍ مسجَّل في أي
    منشأة، فيصير باب الدخول أداة استطلاع.
    """
    from app_core import _verify_password
    from routes.staff_accounts import _NO_GLOBAL_SALT

    data = await request.json()
    db = _db(request)
    client_id = str(data.get("client_id") or "").strip()
    phone = _norm_phone(data.get("phone"))
    password = str(data.get("password") or "")

    fail = HTTPException(status_code=401, detail="بيانات الدخول غير صحيحة")
    if not client_id or not phone or not password:
        raise fail

    row = db.execute(
        """SELECT id, full_name, pass_hash, pass_salt, is_active
           FROM visitors WHERE client_id=%s AND phone=%s""",
        (client_id, phone), fetch="one",
    )
    if not row:
        raise fail
    row = dict(row)
    if not row.get("is_active"):
        raise fail
    # النمط نفسه المستعمل لحسابات الموظفين: ملح الحساب وحده، بلا
    # احتياطٍ للملح العام القديم — `pass_salt` هنا NOT NULL.
    if not _verify_password(password, row, _NO_GLOBAL_SALT):
        raise fail

    db.execute("UPDATE visitors SET last_login=NOW() WHERE id=%s", (row["id"],))
    token = visitor_session.create(request, row["id"], client_id)
    response = JSONResponse({"success": True, "data": {"full_name": row["full_name"]}})
    if token:
        visitor_session.attach_cookie(response, token)
    return response


@router.post("/logout")
async def visitor_logout(request: Request):
    visitor_session.revoke(request, request.cookies.get(visitor_session.COOKIE_NAME))
    response = JSONResponse({"success": True})
    response.delete_cookie(visitor_session.COOKIE_NAME)
    return response


@router.get("/me")
async def visitor_me(request: Request):
    """من أنا — بلا رقم هوية لأن الزائر لا يُدخلها أصلاً."""
    session = require_visitor(request)
    return {"success": True, "data": {
        "kind": "visitor",
        "full_name": session.get("full_name"),
        "phone": session.get("phone"),
    }}


# ── ما يراه الزائر من المنشأة ───────────────────────────────────
@router.get("/rooms")
async def visitor_rooms(request: Request):
    """
    أنواع الغرف وأسعارها — **مُجمَّعةً لا مُفصَّلة**.

    عرض أرقام الغرف وحالاتها للزائر يكشف إشغال المنشأة ومن فيها.
    يكفيه أن يعرف: «جناح · متاح · ٦٠٠ ر.س».
    """
    session = require_visitor(request)
    db = _db(request)
    rows = db.execute(
        """SELECT room_type, COUNT(*) AS available, MIN(base_price) AS price
           FROM rooms
           WHERE client_id=%s AND status='available'
           GROUP BY room_type ORDER BY MIN(base_price)""",
        (session["client_id"],), fetch="all",
    )
    return {"success": True, "data": [
        {"room_type": r["room_type"],
         "available": int(r["available"] or 0),
         "price": float(r["price"] or 0)}
        for r in (rows or [])
    ]}


# ── طلبات الحجز ─────────────────────────────────────────────────
@router.get("/bookings")
async def visitor_bookings(request: Request):
    """طلبات هذا الزائر وحده — `visitor_id` من الجلسة لا من الطلب."""
    session = require_visitor(request)
    db = _db(request)
    rows = db.execute(
        """SELECT id, room_type, check_in, check_out, guests_count, status, created_at
           FROM visitor_bookings
           WHERE client_id=%s AND visitor_id=%s
           ORDER BY created_at DESC LIMIT 50""",
        (session["client_id"], session["visitor_id"]), fetch="all",
    )
    return {"success": True, "data": [dict(r) for r in (rows or [])]}


@router.post("/bookings")
async def visitor_request_booking(request: Request):
    """
    طلب حجزٍ **للزائر نفسه**.

    لا حقل اسمٍ هنا ولا رقم هوية: صاحب الطلب هو صاحب الجلسة. إضافة
    حقل اسمٍ كانت ستجعل البوابة باب إدخال هوياتٍ لا يملكها المُدخِل.
    """
    session = require_visitor(request)
    data = await request.json()
    db = _db(request)
    cid, vid = session["client_id"], session["visitor_id"]

    try:
        check_in = date.fromisoformat(str(data.get("check_in") or "")[:10])
        check_out = date.fromisoformat(str(data.get("check_out") or "")[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail="تواريخ غير صحيحة") from None
    nights = (check_out - check_in).days
    if nights < 1:
        raise HTTPException(status_code=400, detail="المغادرة بعد الوصول")
    if nights > MAX_NIGHTS:
        raise HTTPException(status_code=400, detail=f"الحدّ {MAX_NIGHTS} ليلة")
    if check_in < date.today():
        raise HTTPException(status_code=400, detail="لا يمكن الحجز في الماضي")

    try:
        guests = int(data.get("guests_count") or 1)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="عدد النزلاء غير صحيح") from None
    if not 1 <= guests <= 20:
        raise HTTPException(status_code=400, detail="عدد النزلاء بين ١ و٢٠")

    # `client_id` هنا فائضٌ منطقياً — الزائر يخصّ منشأةً واحدة — لكن
    # القاعدة مطلقة: كل استعلامٍ على جدولٍ يحمل `client_id` يُصفّى به.
    # الاستثناء «الآمن اليوم» هو ما يصير ثغرةً حين يتغيّر ما حوله.
    pending = count_of(db.execute(
        """SELECT COUNT(*) FROM visitor_bookings
           WHERE client_id=%s AND visitor_id=%s AND status='pending'""",
        (cid, vid), fetch="one",
    ))
    if pending >= MAX_PENDING:
        raise HTTPException(
            status_code=429,
            detail=f"لديك {pending} طلبات قيد المراجعة — انتظر ردّ المنشأة",
        )

    booking_id = "VB" + secrets.token_hex(6).upper()
    db.execute(
        """INSERT INTO visitor_bookings
           (id, client_id, visitor_id, room_type, check_in, check_out, guests_count, notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (booking_id, cid, vid, str(data.get("room_type") or "")[:50] or None,
         check_in, check_out, guests, str(data.get("notes") or "")[:500] or None),
    )
    log.info("طلب حجز زائر %s للمنشأة %s", booking_id, cid)
    return {"success": True, "data": {"id": booking_id, "status": "pending"},
            "note": "وصل طلبك — تؤكّده المنشأة وتتواصل معك"}


@router.delete("/bookings/{booking_id}")
async def visitor_cancel(booking_id: str, request: Request):
    """
    إلغاء طلبٍ لم يُؤكَّد بعد.

    الشرط على `visitor_id` **وعلى الحالة**: بدون الأول يُلغي الزائر
    طلب غيره، وبدون الثانية يُلغي حجزاً أكّدته المنشأة وحضّرت له غرفة.
    """
    session = require_visitor(request)
    db = _db(request)
    row = db.execute(
        """DELETE FROM visitor_bookings
           WHERE id=%s AND client_id=%s AND visitor_id=%s AND status='pending'
           RETURNING id""",
        (booking_id, session["client_id"], session["visitor_id"]), fetch="one",
    )
    if not row:
        raise HTTPException(
            status_code=404, detail="الطلب غير موجود أو لا يمكن إلغاؤه بعد التأكيد"
        )
    return {"success": True}
