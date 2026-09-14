#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/public_booking.py — منطق الحجز المباشر العامّ (API منفصل مثل Booking).

الزائر يبحث عبر كل المنشآت التي تستخدم ضيوف ويحجز **مباشرة** على أي فندقٍ أو
شقةٍ مخدومة منشورة. هذا الملف يحمل المنطق **الخالص** (تحقّق التواريخ · التسعير
· تداخل الحجوزات · توليد المرجع) كي يُختبَر بالكسر؛ ولمس القاعدة في المسار.

مبادئ لا تُخالَف:
- **مصدر التوفّر ضيوف**: لا حجزٌ يتداخل مع حجزٍ قائمٍ لنفس الوحدة (منع Overbooking).
- **العزل**: كل حجزٍ يحمل `client_id` (المنشأة) ويُصفّى به.
- **لا كشف**: المرجع لا يكشف بيانات نزيلٍ آخر؛ الاستعلام بالمرجع + الجوال.
"""
from __future__ import annotations

import secrets
from datetime import date

from services import billing_money

MAX_NIGHTS = 365
MAX_GUESTS = 50
VAT_RATE = 0.15


class BookingError(ValueError):
    """خطأ حجزٍ برسالةٍ عربية للزائر."""


def new_ref() -> str:
    """مرجع حجزٍ عامّ فريد (غير قابلٍ للتخمين)."""
    return "PB" + secrets.token_hex(5).upper()


def parse_stay(check_in, check_out, today: date | None = None) -> tuple[date, date, int]:
    """يتحقّق من التواريخ ويعيد (الوصول، المغادرة، الليالي). يرفع BookingError."""
    today = today or date.today()
    try:
        ci = date.fromisoformat(str(check_in or "")[:10])
        co = date.fromisoformat(str(check_out or "")[:10])
    except ValueError:
        raise BookingError("تواريخ غير صحيحة") from None
    nights = (co - ci).days
    if nights < 1:
        raise BookingError("تاريخ المغادرة يجب أن يكون بعد الوصول")
    if nights > MAX_NIGHTS:
        raise BookingError(f"الحدّ الأقصى {MAX_NIGHTS} ليلة")
    if ci < today:
        raise BookingError("لا يمكن الحجز في تاريخٍ ماضٍ")
    return ci, co, nights


def validate_guests(guests, capacity: int) -> int:
    """عدد نزلاءٍ صحيحٌ ضمن سعة الوحدة. يرفع BookingError."""
    try:
        g = int(guests or 1)
    except (TypeError, ValueError):
        raise BookingError("عدد النزلاء غير صحيح") from None
    if not 1 <= g <= MAX_GUESTS:
        raise BookingError(f"عدد النزلاء بين ١ و{MAX_GUESTS}")
    if capacity and g > capacity:
        raise BookingError(f"تتّسع الوحدة لـ{capacity} نزلاء كحدٍّ أقصى")
    return g


def quote(base_price, nights: int, weekend_price=None, weekend_nights: int = 0,
          vat_rate: float = VAT_RATE) -> dict:
    """تسعير الإقامة: ليالٍ × سعر + ضريبة. يعيد {subtotal, vat, total, nights}.

    weekend_nights ليالي نهاية الأسبوع تُسعَّر بسعرها إن وُجد.
    """
    try:
        base = round(float(base_price or 0), 2)
    except (TypeError, ValueError):
        raise BookingError("سعرٌ غير صالح للوحدة") from None
    if base <= 0:
        raise BookingError("الوحدة غير مسعّرة")
    wk = None
    if weekend_price not in (None, "", 0):
        try:
            wk = round(float(weekend_price), 2)
        except (TypeError, ValueError):
            wk = None
    wknd = min(max(int(weekend_nights or 0), 0), nights)
    weekday = nights - wknd
    subtotal = round(weekday * base + wknd * (wk if wk else base), 2)
    v = billing_money.add_vat(subtotal, vat_rate)
    return {"nights": nights, "unit_price": base, "subtotal": v["base"],
            "vat": v["vat"], "total": v["total"]}


def overlaps(a_in: date, a_out: date, b_in: date, b_out: date) -> bool:
    """هل تتداخل إقامتان؟ (نصف مفتوح: المغادرة يومَ وصولِ التالي لا تتداخل)."""
    return a_in < b_out and a_out > b_in
