#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_tenant_isolation.py — حارس العزل بين المنشآت

يفحص **كل** استعلام على جدول يخصّ المستأجرين في `routes/` ويرفض أيّ
واحد بلا شرط `client_id`.

لماذا اختبارٌ ساكن لا اختبار طلبات؟ لأن اختبار الطلبات يفحص المسارات
التي تخطر ببال كاتبه فقط، بينما هذا يفحص ما هو مكتوب فعلاً — فلا يمرّ
استعلام جديد بلا عزل حتى لو لم يكتب أحد اختباراً له.

الاستعلامات المبنيّة ديناميكياً (`WHERE {where}`) تُفكَّك شروطها من
قائمة `conditions` في نفس الدالة، فلا تُعدّ مخالفة لمجرد أنها f-string.
"""
from __future__ import annotations

import ast
import pathlib

ROUTES_DIR = pathlib.Path(__file__).resolve().parent.parent / "routes"

# الجداول التي تحمل عمود client_id — أي استعلام عليها يجب أن يُصفّى به
TENANT_TABLES = {
    "guests", "bookings", "rooms", "invoices", "employees", "pos_sales",
    "maintenance_orders", "warehouse_items", "housekeeping_tasks",
    "booking_reviews", "attendance", "payroll", "channel_configs",
    "channel_reservations", "pricing_rules", "tourism_trips", "destinations",
    "crm_contacts", "check_in_log", "zatca_invoices", "revenue_transactions",
    "staff_users",
}

# استثناءات مُبرَّرة — كل واحد يحمل سبباً، ولا يُضاف إليها بلا مراجعة
ALLOWED = {
    # التحقق العام من فاتورة بمسح رمز QR: عامٌ بطبيعته، والمُدخل نفسه
    # (qr_tlv_base64) هو السر. لا يُعيد معرّفات داخلية — راجع verify_qr.
    ("zatca.py", "verify_qr"),
    # استعلام حالة حجزٍ عامّ بالمرجع (PB+hex غير قابل للتخمين) + الجوال:
    # المرجع نفسه هو السر، والزائر لا يملك client_id. لا كشف عبر المنشآت.
    ("public_booking.py", "reservation_status"),
}


def _sql_of(call: ast.Call) -> str:
    """يُعيد نص SQL من أول وسيط، مع تجميع التسلسل و f-strings."""
    parts: list[str] = []

    def walk(node: ast.AST) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            parts.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            for v in node.values:
                walk(v)
        elif isinstance(node, ast.FormattedValue):
            parts.append(" {} ")
        elif isinstance(node, ast.BinOp):
            walk(node.left)
            walk(node.right)

    walk(call.args[0])
    return " ".join("".join(parts).split())


def _enclosing_function(tree: ast.AST, node: ast.AST) -> str:
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(fn):
                if sub is node:
                    return fn.name
    return "<module>"


def _function_mentions_client_id(tree: ast.AST, node: ast.AST) -> bool:
    """هل تبني الدالةُ الحاويةُ شرطَ client_id في مكان آخر (conditions list)؟"""
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(sub is node for sub in ast.walk(fn)):
                return "client_id" in ast.unparse(fn)
    return False


def collect_violations() -> list[str]:
    violations: list[str] = []
    for path in sorted(ROUTES_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "execute"
                and node.args
            ):
                continue

            sql = _sql_of(node).lower()
            if not sql or not any(k in sql for k in ("select", "update", "delete")):
                continue
            if not any(t in sql for t in TENANT_TABLES):
                continue
            if "client_id" in sql:
                continue

            func = _enclosing_function(tree, node)
            if (path.name, func) in ALLOWED:
                continue
            # شرط مبني ديناميكياً داخل نفس الدالة
            if "{}" in sql and _function_mentions_client_id(tree, node):
                continue

            violations.append(f"{path.name}:{node.lineno} في {func}() — {sql[:90]}")
    return violations


def test_every_tenant_query_filters_by_client_id() -> None:
    """لا استعلام على جدول مستأجرين بلا شرط client_id."""
    violations = collect_violations()
    assert not violations, (
        "استعلامات بلا عزل بين المنشآت (كل واحد تسريبٌ محتمل عبر المستأجرين):\n  "
        + "\n  ".join(violations)
    )


def test_allowlist_entries_still_exist() -> None:
    """يمنع بقاء استثناء في ALLOWED بعد حذف دالته — فلا يتراكم استثناء ميت."""
    stale = []
    for filename, func in ALLOWED:
        path = ROUTES_DIR / filename
        if not path.exists():
            stale.append(f"{filename} — الملف غير موجود")
            continue
        names = {
            n.name
            for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if func not in names:
            stale.append(f"{filename}:{func} — الدالة غير موجودة")
    assert not stale, "استثناءات ميتة في ALLOWED:\n  " + "\n  ".join(stale)
