#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_core_tables_bootstrap.py — ضمان إنشاء الجداول الأساسية

العيب: على قاعدةٍ نظيفة كانت جداولٌ تُنشأ كسولاً أو ضمن ملفٍ يُقسَّم
(pos_sales · branches · staff_roles · staff_role_assignments ·
secure_file_links · audit_log) تبقى غير موجودة، فتعيد المسارات التي
تلمسها 500 — وهذا سبب فشل وظيفة E2E.

الإصلاح: `ensure_core_tables` تُنشئها صراحةً بترتيب التبعية، وتُستدعى من
`run_all_migrations`. يحرس هذا الاختبار وجود الضمان وترتيبه دون الحاجة
إلى PostgreSQL (فحص مصدرٍ).
"""
from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ensure_core_tables_covers_the_missing_tables():
    from db import schema_core_tables as m

    src = (ROOT / "db" / "schema_core_tables.py").read_text(encoding="utf-8")
    for t in ("employees", "branches", "staff_roles", "staff_role_assignments",
              "secure_file_links", "pos_sales", "audit_log"):
        assert f"CREATE TABLE IF NOT EXISTS {t}" in src, f"جدولٌ ناقص: {t}"
    assert hasattr(m, "ensure_core_tables")


def test_dependency_order_is_correct():
    """employees قبل staff_role_assignments، و branches قبل secure_file_links."""
    src = (ROOT / "db" / "schema_core_tables.py").read_text(encoding="utf-8")
    pos = {t: src.index(f"CREATE TABLE IF NOT EXISTS {t}")
           for t in ("employees", "branches", "staff_role_assignments", "secure_file_links")}
    assert pos["employees"] < pos["staff_role_assignments"]
    assert pos["branches"] < pos["secure_file_links"]


def test_run_all_migrations_calls_ensure_core_tables():
    src = (ROOT / "db" / "migrations.py").read_text(encoding="utf-8")
    assert "ensure_core_tables" in src
    # يُستدعى داخل run_all_migrations لا في مكانٍ معزول
    body = src[src.index("def run_all_migrations"):]
    assert "ensure_core_tables(db)" in body


def test_statements_are_individually_isolated():
    """كل عبارةٍ تُنفَّذ وحدها (لا تُسقطها عبارةٌ أخرى)."""
    src = (ROOT / "db" / "schema_core_tables.py").read_text(encoding="utf-8")
    assert re.search(r"for stmt in _STATEMENTS", src)
    assert "try:" in src and "db.execute(stmt)" in src
