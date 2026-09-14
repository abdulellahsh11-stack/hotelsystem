#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/maintenance_report.py — موقع تذكرة الصيانة وتقريرها (منطق خالص).

عند فتح تذكرة صيانة يُحدَّد الموقع: **غرفة · ممر · خارج · دور** (مع وصفٍ
اختياري مثل «الدور ٢» أو «الممر الشرقي»). وعند الإنجاز يُكتب التقرير
(«تم فحص الإضاءة الصفراء وهي تالفة وتم الاستبدال…») وتُخصَم المواد المستخدَمة
من مستودع الصيانة تلقائياً.

خالصٌ: التحقق من نوع الموقع وتشذيب التقرير — لا لمسٌ للقاعدة هنا.
"""
from __future__ import annotations

# أنواع المواقع المسموحة ووسومها العربية.
LOCATION_TYPES = {
    "room": "غرفة",
    "corridor": "ممر",
    "outside": "خارج",
    "floor": "دور",
}


def normalize_location(location_type) -> str | None:
    """نوع موقعٍ معروفٌ أو None (فلا يُخزَّن نوعٌ مبهم)."""
    t = str(location_type or "").strip().lower()
    return t if t in LOCATION_TYPES else None


def location_label(location_type, label) -> str:
    """وصفٌ للعرض: «غرفة — ١٠١» أو «ممر — الشرقي»، أو الوسم وحده."""
    ar = LOCATION_TYPES.get(normalize_location(location_type) or "", "")
    lbl = str(label or "").strip()
    if ar and lbl:
        return f"{ar} — {lbl}"
    return ar or lbl


def clean_report(text) -> str:
    """يشذّب نصّ التقرير (بحدٍّ أقصى معقول)."""
    return str(text or "").strip()[:2000]
