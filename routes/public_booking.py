#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/public_booking.py — API الحجز المباشر العامّ (منفصل، مثل Booking).

بادئة مستقلّة ومُوسَّمة `/api/v1/booking`: الزائر يبحث عبر كل الفنادق والشقق
المخدومة المنشورة التي تستخدم ضيوف ويحجز **مباشرة** بلا حساب — يكفي اسمٌ وجوال.

    GET  /api/v1/booking/units                  بحثٌ في الوحدات المتاحة
    GET  /api/v1/booking/units/{cid}/{unit_id}  تفاصيل وحدة + توفّرها لمدة
    POST /api/v1/booking/reserve                حجزٌ مباشر (منع تداخل + إيديمبوتنسي)
    GET  /api/v1/booking/reservations/{ref}     حالة الحجز بالمرجع + الجوال

**لا يُعرض إلا المنشور**، ولا يُكشف رقم غرفةٍ ولا نزيل، والتوفّر مصدره ضيوف
فلا حجزٌ يتداخل مع قائم. كل قيمةٍ مُمعلَمة (مسارٌ عامّ بلا جلسة).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from services import public_booking as pb

router = APIRouter(prefix="/api/v1/booking", tags=["Public Booking"])
log = logging.getLogger("dheuof.public_booking")

_ACTIVE = "('confirmed','pending_payment')"


def _db(request: Request):
    db = request.app.state.db
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="الخدمة غير متاحة مؤقتاً")
    return db


@router.get("/units")
async def search_units(
    request: Request,
    city: str = Query("", max_length=120),
    kind: str = Query("", max_length=20),
    guests: int = Query(0, ge=0, le=50),
    check_in: str = Query("", max_length=10),
    check_out: str = Query("", max_length=10),
    page: int = Query(1, ge=1, le=200),
    per_page: int = Query(24, ge=1, le=60),
):
    """وحداتٌ منشورة متاحة. لو مُرّرت التواريخ تُستبعَد المحجوزة فيها."""
    db = _db(request)
    where = ["l.is_published = TRUE", "p.is_published = TRUE"]
    params: list = []
    if city.strip():
        where.append("p.city ILIKE %s")
        params.append(f"%{city.strip()}%")
    if kind.strip():
        where.append("l.kind = %s")
        params.append(kind.strip())
    if guests > 0:
        where.append("l.capacity >= %s")
        params.append(guests)
    if check_in and check_out:
        try:
            ci, co, _ = pb.parse_stay(check_in, check_out)
        except pb.BookingError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        where.append(
            f"""NOT EXISTS (SELECT 1 FROM public_bookings b
                 WHERE b.listing_id=l.id AND b.client_id=l.client_id
                   AND b.status IN {_ACTIVE}
                   AND b.check_in < %s AND b.check_out > %s)""")
        params.extend([co, ci])
    sql = f"""
        SELECT l.id, l.client_id, l.kind, l.title, l.base_price, l.capacity,
               l.min_nights, p.display_name, p.city, p.district, p.cover_url
          FROM listings l JOIN property_profile p ON p.client_id = l.client_id
         WHERE {' AND '.join(where)}
         ORDER BY l.base_price
         LIMIT %s OFFSET %s"""
    params.extend([per_page, (page - 1) * per_page])
    rows = db.execute(sql, tuple(params), fetch="all") or []
    data = [dict(r) | {"base_price": float(dict(r)["base_price"] or 0)} for r in rows]
    return {"success": True, "page": page, "count": len(data), "data": data}


@router.get("/units/{client_id}/{unit_id}")
async def unit_availability(client_id: str, unit_id: int, request: Request,
                            check_in: str = Query("", max_length=10),
                            check_out: str = Query("", max_length=10)):
    """تفاصيل وحدةٍ منشورة + توفّرها وتسعيرها للمدّة (إن مُرّرت التواريخ)."""
    db = _db(request)
    row = db.execute(
        """SELECT l.id, l.client_id, l.kind, l.title, l.description, l.base_price,
                  l.weekend_price, l.capacity, l.min_nights,
                  p.display_name, p.city, p.district, p.cover_url,
                  p.checkin_time, p.checkout_time
             FROM listings l JOIN property_profile p ON p.client_id = l.client_id
            WHERE l.id=%s AND l.client_id=%s
              AND l.is_published=TRUE AND p.is_published=TRUE""",
        (unit_id, client_id), fetch="one")
    if not row:
        raise HTTPException(status_code=404, detail="الوحدة غير متاحة")
    out = dict(row)
    out["base_price"] = float(out.get("base_price") or 0)
    if check_in and check_out:
        try:
            ci, co, nights = pb.parse_stay(check_in, check_out)
        except pb.BookingError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
        clash = db.execute(
            f"""SELECT 1 FROM public_bookings
                 WHERE client_id=%s AND listing_id=%s AND status IN {_ACTIVE}
                   AND check_in < %s AND check_out > %s LIMIT 1""",
            (client_id, unit_id, co, ci), fetch="one")
        out["available"] = not bool(clash)
        out["min_nights_ok"] = nights >= int(out.get("min_nights") or 1)
        if out["available"] and out["min_nights_ok"]:
            out["quote"] = pb.quote(out["base_price"], nights,
                                    weekend_price=out.get("weekend_price"))
    return {"success": True, "data": out}


@router.post("/reserve")
async def reserve(request: Request):
    """حجزٌ مباشر. يتحقّق ويُسعّر ويُدرج بمنع تداخلٍ ذرّي وإيديمبوتنسي."""
    db = _db(request)
    data = await request.json()
    cid = str(data.get("client_id") or "").strip()
    try:
        unit_id = int(data.get("unit_id"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="وحدة غير صحيحة") from None
    name = str(data.get("guest_name") or "").strip()
    phone = str(data.get("guest_phone") or "").strip()
    email = str(data.get("guest_email") or "").strip() or None
    if not name or not phone:
        raise HTTPException(status_code=400, detail="الاسم والجوال مطلوبان")

    unit = db.execute(
        """SELECT l.base_price, l.weekend_price, l.capacity, l.min_nights
             FROM listings l JOIN property_profile p ON p.client_id = l.client_id
            WHERE l.id=%s AND l.client_id=%s
              AND l.is_published=TRUE AND p.is_published=TRUE""",
        (unit_id, cid), fetch="one")
    if not unit:
        raise HTTPException(status_code=404, detail="الوحدة غير متاحة")
    unit = dict(unit)

    try:
        ci, co, nights = pb.parse_stay(data.get("check_in"), data.get("check_out"))
        guests = pb.validate_guests(data.get("guests_count"), int(unit.get("capacity") or 0))
        if nights < int(unit.get("min_nights") or 1):
            raise pb.BookingError(f"أقلّ مدّةٍ لهذه الوحدة {unit['min_nights']} ليلة")
        q = pb.quote(unit["base_price"], nights, weekend_price=unit.get("weekend_price"))
    except pb.BookingError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None

    # إيديمبوتنسي: مفتاح العميل أو مشتقٌّ من (وحدة+تواريخ+جوال).
    idem = str(data.get("idempotency_key") or "").strip() \
        or f"{cid}:{unit_id}:{ci}:{co}:{phone}"
    existing = db.execute(
        "SELECT id, status FROM public_bookings WHERE idempotency_key=%s AND client_id=%s",
        (idem, cid), fetch="one")
    if existing:
        return {"success": True, "duplicate": True, "data": dict(existing)}

    ref = pb.new_ref()
    # إدراجٌ ذرّي محروسٌ بعدم التداخل — لا حجزٌ يتداخل مع قائم (منع Overbooking).
    row = db.execute(
        f"""INSERT INTO public_bookings
              (id, client_id, listing_id, guest_name, guest_phone, guest_email,
               check_in, check_out, nights, guests_count,
               unit_price, subtotal, vat, total, status, idempotency_key)
            SELECT %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'confirmed',%s
            WHERE NOT EXISTS (
              SELECT 1 FROM public_bookings b
               WHERE b.client_id=%s AND b.listing_id=%s AND b.status IN {_ACTIVE}
                 AND b.check_in < %s AND b.check_out > %s)
            RETURNING id, status, total""",
        (ref, cid, unit_id, name, phone, email, ci, co, nights, guests,
         q["unit_price"], q["subtotal"], q["vat"], q["total"], idem,
         cid, unit_id, co, ci), fetch="one")
    if not row:
        raise HTTPException(status_code=409, detail="الوحدة محجوزةٌ في هذه المدّة")
    log.info("حجز عامّ مباشر %s للمنشأة %s وحدة %s", ref, cid, unit_id)
    out = dict(row)
    out["total"] = float(out.get("total") or 0)
    return {"success": True, "data": {**out, "check_in": ci.isoformat(),
            "check_out": co.isoformat(), "nights": nights, **q}}


@router.get("/reservations/{ref}")
async def reservation_status(ref: str, request: Request,
                             phone: str = Query("", max_length=30)):
    """حالة حجزٍ بالمرجع + الجوال (تحقّقٌ خفيف يمنع كشف حجز غيرك)."""
    db = _db(request)
    if not phone.strip():
        raise HTTPException(status_code=400, detail="الجوال مطلوب للاستعلام")
    row = db.execute(
        """SELECT id, listing_id, check_in, check_out, nights, guests_count,
                  total, currency, status, created_at
             FROM public_bookings WHERE id=%s AND guest_phone=%s""",
        (ref.strip()[:20], phone.strip()), fetch="one")
    if not row:
        raise HTTPException(status_code=404, detail="لا يوجد حجزٌ بهذا المرجع")
    out = dict(row)
    out["total"] = float(out.get("total") or 0)
    return {"success": True, "data": out}
