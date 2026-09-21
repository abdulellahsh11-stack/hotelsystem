#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/room_status.py — حالات الغرفة وألوانها: مفردةٌ مضبوطة لا نصٌّ حر

خمس حالاتٍ لا سادس لها، لكلٍّ لونٌ واحدٌ يُقرأ في خريطة الغرف:

    جاهزة   available    أخضر   — نظيفةٌ قابلة للإسكان (تظهر خضراء عند الاختيار)
    مشغولة  occupied     ذهبي   — نزيلٌ بداخلها
    نظافة   cleaning     أزرق   — بعد تسجيل الخروج، حتى يُنظّفها طاقم التنظيف
    صيانة   maintenance  أحمر   — حتى يُغلق العطل موظف الصيانة، فتعود «نظافة»
    ترميم   renovation   رمادي  — خارج الخدمة لترميمٍ ممتد

المصدر واحدٌ هنا: الخادم يرسل التسمية واللون، فتعرضهما كل شاشة بلا أن
تكتب الواجهة ألواناً تتباعد. المسمّيات القديمة (`dirty`، `blocked`…)
تُطبَّع إلى الحالة المكافئة فلا يُكسر صفٌّ سابق.
"""
from __future__ import annotations

# الحالة → التسمية العربية واللون (اسمٌ للـCSS وقيمةٌ ست عشرية للعرض المباشر).
STATUSES: dict[str, dict] = {
    "available":   {"label": "جاهزة",  "color": "green", "hex": "#16a34a"},
    "occupied":    {"label": "مشغولة", "color": "gold",  "hex": "#b45309"},
    "cleaning":    {"label": "نظافة",  "color": "blue",  "hex": "#2563eb"},
    "maintenance": {"label": "صيانة",  "color": "red",   "hex": "#dc2626"},
    "renovation":  {"label": "ترميم",  "color": "gray",  "hex": "#6b7280"},
}

#: ترتيب العرض الثابت في الأسطورة (legend) والملخّصات.
ORDER = ("available", "occupied", "cleaning", "maintenance", "renovation")

#: المسمّيات القديمة → الحالة المعتمدة. صفوفٌ كُتبت قبل توحيد المفردات.
_ALIASES = {
    "dirty": "cleaning",        # كان يُستعمل بدل «نظافة»
    "hk-needed": "cleaning",
    "blocked": "renovation",    # كان يعني «خارج الخدمة»
    "out_of_order": "renovation",
    "out-of-order": "renovation",
    "ready": "available",
    "vacant": "available",
}

DEFAULT = "available"


def normalize(status) -> str:
    """أي مُدخَلٍ → حالةٌ معتمدة. غير المعروف يعود «جاهزة» لا يُكسر."""
    s = str(status or "").strip().lower()
    s = _ALIASES.get(s, s)
    return s if s in STATUSES else DEFAULT


def is_valid(status) -> bool:
    """هل الحالة (بعد التطبيع) واحدةٌ من الخمس؟ — لكن نقبل القديم أيضاً."""
    s = str(status or "").strip().lower()
    return s in STATUSES or s in _ALIASES


def decorate(status) -> dict:
    """الحالة المعتمدة مع تسميتها ولونها — لوحدة العرض في كل شاشة."""
    s = normalize(status)
    meta = STATUSES[s]
    return {"status": s, "label": meta["label"], "color": meta["color"], "hex": meta["hex"]}


def legend() -> list[dict]:
    """أسطورة الخريطة: الحالات الخمس بترتيبها، كلٌّ بتسميته ولونه."""
    return [{"status": s, **STATUSES[s]} for s in ORDER]
