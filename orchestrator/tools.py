#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/tools.py — أدوات الطاقم: تعريفٌ للنموذج + تنفيذٌ على عميل ضيوف

كل أداةٍ لها: مخطّطٌ يراه النموذج (اسم · وصف · مدخلات)، ودالّة تنفيذٍ
تنادي عميل ضيوف وتُرجع نصّاً موجزاً. التنفيذ يمرّ بعميل ضيوف الذي يسجّل
كل نداءٍ في سجلّ الحركة — فلا أداة تعمل بلا أثر.
"""
from __future__ import annotations

import json
from typing import Any

from .dheuof import DheuofClient

# مخطّطات الأدوات كما يراها النموذج (Anthropic tools).
TOOL_SCHEMAS = {
    "get_rooms": {
        "name": "get_rooms",
        "description": "قائمة الغرف وحالاتها الحالية (جاهزة/نظافة/صيانة/…).",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_availability": {
        "name": "get_availability",
        "description": "الغرف المتاحة بين تاريخَي دخولٍ وخروج.",
        "input_schema": {
            "type": "object",
            "properties": {
                "check_in": {"type": "string", "description": "YYYY-MM-DD"},
                "check_out": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "additionalProperties": False,
        },
    },
    "get_bookings": {
        "name": "get_bookings",
        "description": "الحجوزات، مع تصفيةٍ اختياريةٍ بالحالة.",
        "input_schema": {
            "type": "object",
            "properties": {"status": {"type": "string"}},
            "additionalProperties": False,
        },
    },
    "get_guests": {
        "name": "get_guests",
        "description": "قائمة النزلاء المسجّلين.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_inventory": {
        "name": "get_inventory",
        "description": "المخزون التشغيلي (مستلزمات الغرف).",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_accounting_summary": {
        "name": "get_accounting_summary",
        "description": "الملخّص المالي للمنشأة.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "get_invoices": {
        "name": "get_invoices",
        "description": "قائمة الفواتير.",
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
}


def _short(data: Any, limit: int = 1500) -> str:
    """يُوجز نتيجة الأداة نصّاً — لا نُغرق سياق النموذج بحمولةٍ ضخمة."""
    s = json.dumps(data, ensure_ascii=False)
    return s if len(s) <= limit else s[:limit] + "…"


def executors(client: DheuofClient, actor: str) -> dict:
    """يربط اسم كل أداةٍ بدالّة تنفيذٍ على عميل ضيوف باسم الفاعل."""
    return {
        "get_rooms": lambda a: _short(client.rooms(actor)),
        "get_availability": lambda a: _short(
            client.availability(a.get("check_in", ""), a.get("check_out", ""), actor)),
        "get_bookings": lambda a: _short(client.bookings(a.get("status", ""), actor)),
        "get_guests": lambda a: _short(client.guests(actor)),
        "get_inventory": lambda a: _short(client.inventory(actor)),
        "get_accounting_summary": lambda a: _short(client.accounting_summary(actor)),
        "get_invoices": lambda a: _short(client.invoices(actor)),
    }


def schemas_for(tool_names) -> list:
    """مخطّطات الأدوات المسموحة لدورٍ بعينه، كما يتوقّعها Anthropic."""
    return [TOOL_SCHEMAS[n] for n in tool_names if n in TOOL_SCHEMAS]
