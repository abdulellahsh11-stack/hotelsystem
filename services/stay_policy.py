#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/stay_policy.py — سياسة الدخول والخروج، قابلةٌ للتخصيص لكل منشأة

وقتا الدخول والخروج الافتراضيان، والحالات الخاصة (دخولٌ مبكر بلا رسوم،
خروجٌ متأخّر بمقابل). تُخزَّن في `clients.settings["stay_policy"]`
وتُقرأها واجهة التسجيل لعرض التلميح والافتراضات.

التنقية هنا لا في المسار: كل ما يُحفَظ يمرّ من `sanitize` فلا تدخل
قيمةٌ لم تُتحقَّق. القيَم الزمنية بصيغة `HH:MM` والرسوم عددٌ غير سالب.
"""
from __future__ import annotations

import re

# الافتراضات المعتادة في الفندقة السعودية: دخولٌ ٢:٠٠م، خروجٌ ١٢:٠٠م.
DEFAULT: dict = {
    "checkin_time": "14:00",
    "checkout_time": "12:00",
    "early_checkin_free": True,          # دخولٌ مبكر عند توفّر الغرفة بلا رسوم
    "late_checkout_fee_enabled": False,  # خروجٌ متأخّر بمقابل إضافي
    "late_checkout_fee": 200,            # ر.س لكل مدّة
    "late_checkout_block_hours": 3,      # مدّة الاحتساب بالساعات
}

_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _time(value, fallback: str) -> str:
    """`HH:MM` صالحة أو الافتراضي — لا نثق بنصّ الواجهة."""
    s = str(value or "").strip()
    return s if _TIME.match(s) else fallback


def _nonneg_int(value, fallback: int) -> int:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return fallback
    return n if n >= 0 else fallback


def _pos_int(value, fallback: int) -> int:
    n = _nonneg_int(value, fallback)
    return n if n >= 1 else fallback


def sanitize(data: dict) -> dict:
    """يُحوّل مُدخَل الواجهة إلى سياسةٍ موثوقة — كل حقلٍ يُتحقَّق أو يعود لافتراضه."""
    data = data if isinstance(data, dict) else {}
    return {
        "checkin_time": _time(data.get("checkin_time"), DEFAULT["checkin_time"]),
        "checkout_time": _time(data.get("checkout_time"), DEFAULT["checkout_time"]),
        "early_checkin_free": bool(data.get("early_checkin_free", DEFAULT["early_checkin_free"])),
        "late_checkout_fee_enabled": bool(
            data.get("late_checkout_fee_enabled", DEFAULT["late_checkout_fee_enabled"])
        ),
        "late_checkout_fee": _nonneg_int(data.get("late_checkout_fee"), DEFAULT["late_checkout_fee"]),
        "late_checkout_block_hours": _pos_int(
            data.get("late_checkout_block_hours"), DEFAULT["late_checkout_block_hours"]
        ),
    }


def get_policy(client: dict) -> dict:
    """سياسة المنشأة المحفوظة، مدموجةً فوق الافتراضات (فلا حقلٌ ناقص)."""
    settings = (client or {}).get("settings") or {}
    saved = settings.get("stay_policy") if isinstance(settings, dict) else None
    merged = dict(DEFAULT)
    if isinstance(saved, dict):
        merged.update(saved)
    return sanitize(merged)
