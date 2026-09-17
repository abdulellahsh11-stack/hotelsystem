#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_migrations.py — ترحيلات مستقلة عن مخطط v3 الأساسي

مُستخرَج من `schema_v3.py` ليبقى كل ملف ضمن حدٍّ يُقرأ. يضمّ ما يُطبَّق
**بعد** الجداول الأساسية: تتبّع إجراءات الغرف، وحسابات دخول الموظفين،
وجلسات المنشآت، وفهارس الأداء.

`schema_v3` يُعيد تصدير كل ما هنا، فاستيراداتٌ مثل
`from db.schema_v3 import run_sessions_migration` تبقى صحيحة كما كانت.
"""
from __future__ import annotations

# ── Staff App migrations — room accountability ────────────────────────────────
STAFF_APP_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS room_actions (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50),
    room_number     VARCHAR(20) NOT NULL,
    action_type     VARCHAR(40) NOT NULL,
    performed_by    VARCHAR(100) NOT NULL,
    previous_status VARCHAR(30),
    new_status      VARCHAR(30),
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_room_actions_client ON room_actions(client_id, room_number);
CREATE INDEX IF NOT EXISTS idx_room_actions_staff  ON room_actions(performed_by)
"""

STAFF_ACCOUNTS_SCHEMA = """
-- حسابات دخول الموظفين. منفصلة عن جدول employees عمداً: ذاك سجلٌّ
-- للموارد البشرية (راتب، حضور) وقد يخصّ من لا يستخدم النظام إطلاقاً،
-- وهذا اعتمادُ دخول. خلطهما يعني أن كل موظف مُسجَّل يصير له حساب.
CREATE TABLE IF NOT EXISTS staff_users (
    id           SERIAL PRIMARY KEY,
    client_id    VARCHAR(50) NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    username     VARCHAR(60)  NOT NULL,
    full_name    VARCHAR(200) NOT NULL,
    pass_hash    VARCHAR(255) NOT NULL,
    pass_salt    VARCHAR(64)  NOT NULL,
    role         VARCHAR(40)  NOT NULL,
    extra_perms  TEXT,
    employee_id  INTEGER,
    is_active    BOOLEAN     DEFAULT TRUE,
    last_login   TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    created_by   VARCHAR(60),
    -- اسم المستخدم فريد داخل المنشأة لا عبر المنصة: فندقان مختلفان
    -- يجوز أن يكون في كلٍّ منهما «reception».
    UNIQUE(client_id, username)
);
CREATE INDEX IF NOT EXISTS idx_staff_users_client ON staff_users(client_id, is_active)
"""

STAFF_APP_ALTER = [
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS last_action_by  VARCHAR(100)",
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS last_action_at  TIMESTAMPTZ",
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS current_guest   VARCHAR(200)",
    "ALTER TABLE rooms ADD COLUMN IF NOT EXISTS checkout_due    VARCHAR(10)",
    # سجلّ المساءلة: من سجّل النزيل. اسمُ من أدخل البيانات يُحفَظ مع الصفّ
    # كي يُعرَف لاحقاً — لا يُشتق من جلسةٍ انتهت.
    "ALTER TABLE guests ADD COLUMN IF NOT EXISTS created_by VARCHAR(100)",
    # سرّ توقيع حجوزات القنوات. عمودٌ مستقل لا مفتاحٌ في settings، لأن
    # settings تُعاد كاملةً إلى الواجهة فيخرج السرّ معها.
    "ALTER TABLE clients ADD COLUMN IF NOT EXISTS channel_secret VARCHAR(64)",
    # رقم الحجز المقروء. غيابه كان يُفشل **كل** تسجيل دخول ومغادرة:
    # سلسلة التكامل تطلبه بـ RETURNING، والمحاسبة تختاره في استعلاماتها.
    # ولأن السلسلة داخل معاملة، كان الفشل يُرجع كل شيء: الغرفة لا تصير
    # مشغولة ولا يُسجَّل إيراد ولا يُخصم من المستودع.
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS booking_number VARCHAR(50)",
    # الصفوف القائمة تأخذ معرّفها رقماً لها، فلا يبقى حجزٌ بلا رقم
    "UPDATE bookings SET booking_number = id WHERE booking_number IS NULL",
]


def run_staff_app_migrations(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.staff_app")
    if not db.use_postgres:
        return
    for stmt in STAFF_APP_MIGRATIONS.split(";"):
        s = stmt.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.warning(f"staff_app migration: {e}")
    for stmt in STAFF_APP_ALTER:
        try:
            db.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"ALTER rooms: {e}")
    for stmt in STAFF_ACCOUNTS_SCHEMA.split(";"):
        s = stmt.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.warning(f"staff_users migration: {e}")
    log.info("✅ Staff App migrations — room_actions + accountability + staff_users")


NEW_TRIGGERS = [
    ("trg_gp_updated",   "guest_profiles"),
    ("trg_emp_updated",  "employees"),
]

# ── Sessions table migration ────────────────────────────────────────────────
SESSIONS_MIGRATION = """
CREATE TABLE IF NOT EXISTS client_sessions (
    token       VARCHAR(64) PRIMARY KEY,
    client_id   VARCHAR(50) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL,
    user_agent  TEXT,
    ip_address  VARCHAR(50)
);
CREATE INDEX IF NOT EXISTS idx_csess_client ON client_sessions(client_id);
CREATE INDEX IF NOT EXISTS idx_csess_exp    ON client_sessions(expires_at)
"""


# هوية صاحب الجلسة. بدونها تُبنى الجلسة المستعادة بدورٍ مُثبَّت في
# الكود، فيصير كل من يستعيد جلسته مالكاً.
SESSION_IDENTITY_COLUMNS = [
    "ALTER TABLE client_sessions ADD COLUMN IF NOT EXISTS role VARCHAR(40)",
    "ALTER TABLE client_sessions ADD COLUMN IF NOT EXISTS staff_id INTEGER",
    "ALTER TABLE client_sessions ADD COLUMN IF NOT EXISTS username VARCHAR(60)",
    "ALTER TABLE client_sessions ADD COLUMN IF NOT EXISTS full_name VARCHAR(200)",
    "ALTER TABLE client_sessions ADD COLUMN IF NOT EXISTS permissions TEXT",
]


def run_sessions_migration(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.sessions")
    if not db.use_postgres:
        return
    for stmt in SESSIONS_MIGRATION.split(";"):
        s = stmt.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.warning(f"sessions migration: {e}")
    # أعمدة الهوية **بعد** إنشاء الجدول لا قبله.
    # كانت في ترحيل تطبيق الموظفين الذي يسبقه، فتفشل كلها على قاعدة
    # جديدة ولا تُضاف أبداً — فلا تُحفظ جلسة ولا تُستعاد، ويُطرد
    # المستخدمون مع كل إعادة تشغيل بلا سبب ظاهر.
    for stmt in SESSION_IDENTITY_COLUMNS:
        try:
            db.execute(stmt)
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"sessions identity columns: {e}")
    log.info("✅ client_sessions table ready")


# ── Row Level Security — defense-in-depth for multi-tenant isolation ────────

RLS_POLICIES = """
-- ================================================================
-- Row Level Security — enforced at DB layer (defense in depth)
-- Note: app layer already enforces client_id; RLS adds DB-layer guarantee
-- ================================================================
ALTER TABLE guests ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE warehouse_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE maintenance_orders ENABLE ROW LEVEL SECURITY;

-- Application role must SET app.current_client_id before queries
-- CREATE POLICY guest_isolation ON guests USING (client_id = current_setting('app.current_client_id', true));
-- (Commented: enable when app sets session variable per request)

-- For now, ensure all tables have RLS enabled (blocks direct DB access without policy)
"""


def run_rls_migration(db) -> None:
    """Enable RLS on all tenant tables (idempotent — ALTER TABLE ... ENABLE is safe to re-run)."""
    if not db.use_postgres:
        return
    for stmt in RLS_POLICIES.strip().split("\n"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--") and not stmt.startswith("CREATE"):
            try:
                db.execute(stmt)
            except Exception as e:
                err = str(e).lower()
                if "does not exist" not in err:
                    import logging
                    logging.getLogger("dheuof").warning(f"RLS migration: {e}")


# ── Performance indexes for hot multi-tenant query paths ────────────────────
PERF_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_bookings_client_status   ON bookings(client_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_client_checkin  ON bookings(client_id, check_in);
CREATE INDEX IF NOT EXISTS idx_bookings_client_checkout ON bookings(client_id, check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_client_room     ON bookings(client_id, room_id);
CREATE INDEX IF NOT EXISTS idx_rooms_client_status      ON rooms(client_id, status);
CREATE INDEX IF NOT EXISTS idx_guests_client_created    ON guests(client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_employees_client_status  ON employees(client_id, status);
CREATE INDEX IF NOT EXISTS idx_maint_client_status      ON maintenance_orders(client_id, status);
CREATE INDEX IF NOT EXISTS idx_checkin_client_date      ON check_in_log(client_id, checked_in_at);
CREATE INDEX IF NOT EXISTS idx_wmov_client              ON warehouse_movements(client_id, created_at);
"""


def run_perf_indexes(db) -> None:
    """Create composite indexes on (client_id, hot_column) for fast tenant queries.

    Idempotent — every statement is CREATE INDEX IF NOT EXISTS. Failures on a
    not-yet-created table are ignored (the table's own migration runs elsewhere).
    """
    if not db.use_postgres:
        return
    import logging
    log = logging.getLogger("dheuof")
    for stmt in PERF_INDEXES.strip().split(";"):
        s = stmt.strip()
        if s and not s.startswith("--"):
            try:
                db.execute(s)
            except Exception as e:
                err = str(e).lower()
                if "does not exist" not in err and "already exists" not in err:
                    log.warning(f"perf index: {e}")
