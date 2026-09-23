#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_core_tables.py — إنشاءٌ صريحٌ وحصينٌ للجداول الأساسية.

المشكلة: بعض الجداول (`pos_sales` عبر `_ensure_pos_table` عند أوّل طلب،
و`branches`/`staff_roles`/`staff_role_assignments`/`secure_file_links`/`audit_log`
عبر ملف التحصين) تُنشأ كسولاً أو ضمن ملفٍ يُقسَّم فتفشل عبارةٌ تابعةٌ فتُسقط
معها جداول صحيحة. على قاعدةٍ نظيفة (E2E) تبقى هذه الجداول غير موجودة،
فتعيد المسارات التي تلمسها 500.

الحلّ: إنشاؤها هنا صراحةً — كلٌّ في عبارةٍ مستقلّة تُثبَّت وحدها (لا تُسقطها
عبارةٌ أخرى)، وبترتيب التبعية (employees قبل staff_role_assignments،
branches قبل secure_file_links). آمنٌ للتشغيل أكثر من مرّة (IF NOT EXISTS)،
ولا يمسّ الإنتاج لأنه لا يُعيد إنشاء جدولٍ قائم.

التعاريف منسوخةٌ حرفياً من مصادرها القانونية:
- employees            ← db/schema_v3.py
- pos_sales            ← routes/pos.py
- staff_roles /        ← specs/db/04-isolation-hardening.sql
  staff_role_assignments
- branches /           ← specs/db/04-isolation-hardening.sql
  secure_file_links
- audit_log            ← specs/db/hotel-system-ddl.sql
"""
from __future__ import annotations
import logging

log = logging.getLogger("dheuof.db.core_tables")

# ترتيب التبعية مهمّ: كلُّ جدولٍ بعد ما يشير إليه.
_STATEMENTS: list[str] = [
    # employees — يسبق staff_role_assignments التي تشير إليه
    """CREATE TABLE IF NOT EXISTS employees (
        id              SERIAL PRIMARY KEY,
        client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
        employee_id     VARCHAR(30) NOT NULL,
        full_name_ar    VARCHAR(150) NOT NULL,
        full_name_en    VARCHAR(150),
        national_id     VARCHAR(20),
        iqama_number    VARCHAR(20),
        nationality     VARCHAR(50),
        position        VARCHAR(100),
        department      VARCHAR(100),
        phone           VARCHAR(20),
        email           VARCHAR(100),
        hire_date       DATE,
        basic_salary    DECIMAL(10,2) DEFAULT 0,
        housing_allow   DECIMAL(10,2) DEFAULT 0,
        transport_allow DECIMAL(10,2) DEFAULT 0,
        status          VARCHAR(20) DEFAULT 'active',
        notes           TEXT,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(client_id, employee_id)
    )""",
    # branches — يسبق secure_file_links والـ branch_id refs
    """CREATE TABLE IF NOT EXISTS branches (
        id          SERIAL PRIMARY KEY,
        client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
        branch_code VARCHAR(30) NOT NULL,
        name_ar     VARCHAR(150) NOT NULL,
        city        VARCHAR(100),
        is_active   BOOLEAN DEFAULT TRUE,
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(client_id, branch_code)
    )""",
    # staff_roles
    """CREATE TABLE IF NOT EXISTS staff_roles (
        id          SERIAL PRIMARY KEY,
        client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
        role_code   VARCHAR(30) NOT NULL,
        name_ar     VARCHAR(100) NOT NULL,
        permissions JSONB DEFAULT '[]',
        created_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(client_id, role_code)
    )""",
    # staff_role_assignments — يشير إلى employees و clients
    """CREATE TABLE IF NOT EXISTS staff_role_assignments (
        id          SERIAL PRIMARY KEY,
        client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
        employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
        role_code   VARCHAR(30) NOT NULL,
        branch_id   INTEGER,
        granted_by  VARCHAR(100),
        granted_at  TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(client_id, employee_id, role_code)
    )""",
    # secure_file_links — يشير إلى branches و guests و clients
    """CREATE TABLE IF NOT EXISTS secure_file_links (
        id          SERIAL PRIMARY KEY,
        client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
        branch_id   INTEGER REFERENCES branches(id),
        guest_id    INTEGER REFERENCES guests(id),
        file_path   TEXT NOT NULL,
        link_token  VARCHAR(128) UNIQUE NOT NULL,
        expires_at  TIMESTAMPTZ NOT NULL,
        created_by  VARCHAR(100),
        created_at  TIMESTAMPTZ DEFAULT NOW()
    )""",
    # pos_sales — تُنشأ كسولاً في routes/pos.py؛ نضمنها هنا لأجل هجرات v4
    """CREATE TABLE IF NOT EXISTS pos_sales (
        id                 SERIAL PRIMARY KEY,
        client_id          VARCHAR(50),
        sale_number        VARCHAR(30),
        guest_id           INTEGER,
        items              JSONB DEFAULT '[]',
        subtotal           DECIMAL(10,2) DEFAULT 0,
        vat_amount         DECIMAL(10,2) DEFAULT 0,
        tourism_tax_amount DECIMAL(10,2) DEFAULT 0,
        total              DECIMAL(10,2) DEFAULT 0,
        tax_mode           VARCHAR(10)   DEFAULT 'MODE_A',
        payment_method     VARCHAR(30)   DEFAULT 'cash',
        status             VARCHAR(20)   DEFAULT 'completed',
        created_by         VARCHAR(100),
        created_at         TIMESTAMPTZ   DEFAULT NOW()
    )""",
    # audit_log — append-only
    """CREATE TABLE IF NOT EXISTS audit_log (
        id              BIGSERIAL PRIMARY KEY,
        client_id       VARCHAR(50),
        user_id         INTEGER,
        user_email      VARCHAR(255),
        action          VARCHAR(100)  NOT NULL,
        resource_type   VARCHAR(100)  NOT NULL,
        resource_id     TEXT,
        old_values      JSONB,
        new_values      JSONB,
        ip_address      INET,
        user_agent      TEXT,
        created_at      TIMESTAMPTZ   DEFAULT NOW()
    )""",
    # فهارس خفيفة (كلٌّ مستقلّة)
    "CREATE INDEX IF NOT EXISTS idx_emp_client ON employees(client_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_branches_client ON branches(client_id, is_active)",
    "CREATE INDEX IF NOT EXISTS idx_sra_client_emp ON staff_role_assignments(client_id, employee_id)",
    "CREATE INDEX IF NOT EXISTS idx_sfl_token ON secure_file_links(link_token, expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_pos_client ON pos_sales(client_id, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_audit_client ON audit_log(client_id, created_at DESC)",
]


def ensure_core_tables(db) -> None:
    """يُنشئ الجداول الأساسية إن غابت — كلٌّ في عبارةٍ مستقلّة تُثبَّت وحدها."""
    if not getattr(db, "use_postgres", False):
        return
    created = 0
    for stmt in _STATEMENTS:
        try:
            db.execute(stmt)
            created += 1
        except Exception as e:  # لا نُوقف الإقلاع على جدولٍ واحد
            log.warning("ensure_core_tables: تعذّرت عبارة (%s): %s",
                        stmt.split("(")[0].strip()[:60], str(e).splitlines()[0])
    log.info("✓ الجداول الأساسية جاهزة (%d/%d عبارة)", created, len(_STATEMENTS))
