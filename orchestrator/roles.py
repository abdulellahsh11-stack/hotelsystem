#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/roles.py — الطاقم: أدوارٌ متخصّصة، كلٌّ بأضيق نطاق يحقّق مهمّته

كل دورٍ = وكيلٌ له تعريفٌ واحد (وصف · تعليمات · أدواتٌ مسموحة). لا وكيل
«عام الغرض»: الاستقبال لا يلمس المحاسبة، والتنظيف لا يرى الفواتير —
كما هرم الصلاحيات في المنصّة نفسها.

الأدوات هنا أسماءٌ منطقية تُنفَّذ في `tools.py` عبر عميل ضيوف. مفتاح
الاشتراك يفرض الحدّ الفعلي على الخادم؛ هذا التخصيص طبقةٌ ثانية للوضوح.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    key: str
    label: str
    description: str
    instructions: str
    tools: tuple           # أسماء الأدوات المسموحة لهذا الدور


RECEPTION = Role(
    key="reception",
    label="موظف استقبال",
    description="الحجوزات والنزلاء والتوافر والغرف",
    instructions=(
        "أنت موظف استقبال في منشأةٍ فندقية. تجيب عن الحجوزات والنزلاء "
        "والغرف المتاحة. استعمل الأدوات لقراءة البيانات الفعلية، ولا تخترع "
        "أرقاماً. أجب بالعربية باختصارٍ ووضوح."
    ),
    tools=("get_rooms", "get_availability", "get_bookings", "get_guests"),
)

HOUSEKEEPING = Role(
    key="housekeeping",
    label="خدمات الغرف",
    description="حالة الغرف والمخزون التشغيلي",
    instructions=(
        "أنت مشرف خدمات الغرف. تتابع حالات الغرف (جاهزة/نظافة/صيانة/ترميم) "
        "والمخزون. لا ترى بيانات النزلاء ولا الفواتير. أجب بالعربية باختصار."
    ),
    tools=("get_rooms", "get_inventory"),
)

MAINTENANCE = Role(
    key="maintenance",
    label="موظف صيانة",
    description="أعطال الغرف وأوامر الصيانة",
    instructions=(
        "أنت موظف صيانة. تتابع الغرف التي تحتاج صيانة وحالتها. أجب بالعربية "
        "باختصار، وحدّد الغرف الحمراء (صيانة) التي تحتاج إغلاق عطل."
    ),
    tools=("get_rooms",),
)

ACCOUNTING = Role(
    key="accounting",
    label="محاسب",
    description="الفواتير والملخّص المالي",
    instructions=(
        "أنت محاسب المنشأة. تقرأ الملخّص المالي والفواتير. لا ترى هويات "
        "النزلاء. أجب بالعربية بأرقامٍ دقيقةٍ من الأدوات لا من التخمين."
    ),
    tools=("get_accounting_summary", "get_invoices"),
)

ROLES = {r.key: r for r in (RECEPTION, HOUSEKEEPING, MAINTENANCE, ACCOUNTING)}
