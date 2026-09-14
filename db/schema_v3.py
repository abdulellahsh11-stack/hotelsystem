#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/schema_v3.py — مخطط قاعدة بيانات ضيوف الكامل v3.0
جميع الوحدات الـ 15 — يعمل مع نظام الـ migrations الحالي
"""

SCHEMA_V3_MODULES = """
-- ================================================================
-- ضيوف Dheuof — Module Tables v3.0
-- ================================================================

-- ──────────────────────────────────────────────────────────────
-- M01: إدارة الضيوف — Guest Management
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS guest_profiles (
    id            SERIAL PRIMARY KEY,
    client_id     VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id      INTEGER REFERENCES guests(id) ON DELETE CASCADE,
    vip_level     VARCHAR(20) DEFAULT 'standard',
    preferred_room_type VARCHAR(50),
    dietary_notes TEXT,
    loyalty_points INTEGER DEFAULT 0,
    total_stays   INTEGER DEFAULT 0,
    total_revenue DECIMAL(12,2) DEFAULT 0,
    tags          JSONB DEFAULT '[]',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_gp_client ON guest_profiles(client_id);
CREATE INDEX IF NOT EXISTS idx_gp_guest  ON guest_profiles(guest_id);

CREATE TABLE IF NOT EXISTS room_types (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,
    name_ar     VARCHAR(100) NOT NULL,
    name_en     VARCHAR(100),
    capacity    INTEGER DEFAULT 2,
    base_price  DECIMAL(10,2) DEFAULT 0,
    amenities   JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, code)
);

CREATE TABLE IF NOT EXISTS rate_plans (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    code        VARCHAR(20) NOT NULL,
    name_ar     VARCHAR(100) NOT NULL,
    rate_type   VARCHAR(30) DEFAULT 'daily',
    base_amount DECIMAL(10,2) NOT NULL,
    min_stay    INTEGER DEFAULT 1,
    max_stay    INTEGER,
    valid_from  DATE,
    valid_to    DATE,
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, code)
);

-- ──────────────────────────────────────────────────────────────
-- M02: الاستقبال — Front Desk
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS front_desk_shifts (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_name   VARCHAR(100) NOT NULL,
    shift_type      VARCHAR(20) DEFAULT 'morning',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ,
    opening_cash    DECIMAL(10,2) DEFAULT 0,
    closing_cash    DECIMAL(10,2),
    notes           TEXT,
    status          VARCHAR(20) DEFAULT 'open'
);
CREATE INDEX IF NOT EXISTS idx_shifts_client ON front_desk_shifts(client_id, started_at);

CREATE TABLE IF NOT EXISTS check_in_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    room_id         INTEGER REFERENCES rooms(id),
    guest_id        INTEGER REFERENCES guests(id),
    checkin_by      VARCHAR(100),
    id_verified     BOOLEAN DEFAULT FALSE,
    key_issued      BOOLEAN DEFAULT FALSE,
    notes           TEXT,
    checked_in_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS check_out_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    checkout_by     VARCHAR(100),
    final_amount    DECIMAL(10,2),
    payment_method  VARCHAR(30),
    notes           TEXT,
    checked_out_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- M06: الموارد البشرية — HR & Payroll
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS employees (
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
);
CREATE INDEX IF NOT EXISTS idx_emp_client ON employees(client_id, status);

CREATE TABLE IF NOT EXISTS attendance (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_id     INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    work_date       DATE NOT NULL,
    check_in_time   TIME,
    check_out_time  TIME,
    hours_worked    DECIMAL(5,2),
    overtime_hours  DECIMAL(5,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'present',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, employee_id, work_date)
);
CREATE INDEX IF NOT EXISTS idx_att_client_date ON attendance(client_id, work_date);

CREATE TABLE IF NOT EXISTS payroll (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    employee_id     INTEGER REFERENCES employees(id) ON DELETE CASCADE,
    period_month    INTEGER NOT NULL,
    period_year     INTEGER NOT NULL,
    basic_salary    DECIMAL(10,2) DEFAULT 0,
    allowances      DECIMAL(10,2) DEFAULT 0,
    overtime_pay    DECIMAL(10,2) DEFAULT 0,
    deductions      DECIMAL(10,2) DEFAULT 0,
    gosi_employee   DECIMAL(10,2) DEFAULT 0,
    gosi_employer   DECIMAL(10,2) DEFAULT 0,
    net_salary      DECIMAL(10,2) DEFAULT 0,
    paid_at         DATE,
    status          VARCHAR(20) DEFAULT 'pending',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, employee_id, period_month, period_year)
);
CREATE INDEX IF NOT EXISTS idx_payroll_client ON payroll(client_id, period_year, period_month);

-- ──────────────────────────────────────────────────────────────
-- M07: الإشراف الداخلي — Housekeeping
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS housekeeping_tasks (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    task_type       VARCHAR(30) DEFAULT 'cleaning',
    priority        VARCHAR(20) DEFAULT 'normal',
    assigned_to     VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'pending',
    notes           TEXT,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_hk_client_status ON housekeeping_tasks(client_id, status);

CREATE TABLE IF NOT EXISTS housekeeping_checklist (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    task_id         INTEGER REFERENCES housekeeping_tasks(id) ON DELETE CASCADE,
    item            VARCHAR(200) NOT NULL,
    checked         BOOLEAN DEFAULT FALSE,
    checked_by      VARCHAR(100),
    checked_at      TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS lost_and_found (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    item_description TEXT NOT NULL,
    found_date      DATE DEFAULT CURRENT_DATE,
    found_by        VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'stored',
    claimed_by      VARCHAR(100),
    claimed_date    DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- M08: الصيانة — Maintenance
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS maintenance_orders (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id         INTEGER REFERENCES rooms(id),
    order_number    VARCHAR(30),
    issue_type      VARCHAR(50),
    description     TEXT NOT NULL,
    priority        VARCHAR(20) DEFAULT 'normal',
    assigned_to     VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'open',
    estimated_cost  DECIMAL(10,2),
    actual_cost     DECIMAL(10,2),
    parts_used      JSONB DEFAULT '[]',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mo_client_status ON maintenance_orders(client_id, status);

CREATE TABLE IF NOT EXISTS assets (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    asset_code      VARCHAR(30) NOT NULL,
    name_ar         VARCHAR(150) NOT NULL,
    category        VARCHAR(50),
    location        VARCHAR(100),
    purchase_date   DATE,
    purchase_cost   DECIMAL(10,2),
    warranty_expiry DATE,
    status          VARCHAR(20) DEFAULT 'operational',
    last_service_at DATE,
    next_service_at DATE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, asset_code)
);
CREATE INDEX IF NOT EXISTS idx_assets_client ON assets(client_id, status);

-- ──────────────────────────────────────────────────────────────
-- M10: CRM والولاء — CRM & Loyalty
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS crm_contacts (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id        INTEGER REFERENCES guests(id),
    segment         VARCHAR(50) DEFAULT 'regular',
    lifecycle_stage VARCHAR(30) DEFAULT 'active',
    lifetime_value  DECIMAL(12,2) DEFAULT 0,
    total_bookings  INTEGER DEFAULT 0,
    last_stay_date  DATE,
    nps_score       INTEGER,
    tags            JSONB DEFAULT '[]',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_crm_client ON crm_contacts(client_id, segment);

CREATE TABLE IF NOT EXISTS loyalty_transactions (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id        INTEGER REFERENCES guests(id),
    transaction_type VARCHAR(30),
    points          INTEGER NOT NULL,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_loyalty_guest ON loyalty_transactions(client_id, guest_id);

CREATE TABLE IF NOT EXISTS campaigns (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    name            VARCHAR(150) NOT NULL,
    campaign_type   VARCHAR(30) DEFAULT 'email',
    target_segment  VARCHAR(50),
    message_ar      TEXT,
    subject         VARCHAR(200),
    send_date       DATE,
    status          VARCHAR(20) DEFAULT 'draft',
    sent_count      INTEGER DEFAULT 0,
    opened_count    INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ──────────────────────────────────────────────────────────────
-- M11: مؤشرات الأداء — KPI Analytics
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_kpis (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    kpi_date        DATE NOT NULL,
    total_rooms     INTEGER DEFAULT 0,
    occupied_rooms  INTEGER DEFAULT 0,
    occupancy_rate  DECIMAL(5,2) DEFAULT 0,
    adr             DECIMAL(10,2) DEFAULT 0,
    revpar          DECIMAL(10,2) DEFAULT 0,
    trevpar         DECIMAL(10,2) DEFAULT 0,
    revenue_rooms   DECIMAL(12,2) DEFAULT 0,
    revenue_fb      DECIMAL(12,2) DEFAULT 0,
    revenue_other   DECIMAL(12,2) DEFAULT 0,
    revenue_total   DECIMAL(12,2) DEFAULT 0,
    check_ins       INTEGER DEFAULT 0,
    check_outs      INTEGER DEFAULT 0,
    no_shows        INTEGER DEFAULT 0,
    cancellations   INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, kpi_date)
);
CREATE INDEX IF NOT EXISTS idx_kpi_client_date ON daily_kpis(client_id, kpi_date);

-- ──────────────────────────────────────────────────────────────
-- M13: المستودعات والمشتريات — Warehouses & Procurement
-- ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS warehouse_items (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    warehouse_type  VARCHAR(30) DEFAULT 'general',
    name            VARCHAR(200) NOT NULL,
    unit            VARCHAR(20) DEFAULT 'قطعة',
    quantity        DECIMAL(10,2) DEFAULT 0,
    reorder_level   DECIMAL(10,2) DEFAULT 0,
    price_per_unit  DECIMAL(10,2) DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wi_client ON warehouse_items(client_id);

CREATE TABLE IF NOT EXISTS warehouse_movements (
    id              SERIAL PRIMARY KEY,
    item_id         INTEGER REFERENCES warehouse_items(id) ON DELETE CASCADE,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    movement_type   VARCHAR(10) DEFAULT 'in',
    quantity        DECIMAL(10,2) NOT NULL,
    notes           TEXT,
    created_by      VARCHAR(100),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    supplier_code   VARCHAR(30),
    name_ar         VARCHAR(150) NOT NULL,
    name_en         VARCHAR(150),
    vat_number      VARCHAR(20),
    contact_phone   VARCHAR(20),
    contact_email   VARCHAR(100),
    payment_terms   INTEGER DEFAULT 30,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sup_client ON suppliers(client_id, status);

CREATE TABLE IF NOT EXISTS purchase_orders (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    po_number       VARCHAR(30) NOT NULL,
    supplier_id     INTEGER REFERENCES suppliers(id),
    order_date      DATE DEFAULT CURRENT_DATE,
    expected_date   DATE,
    status          VARCHAR(20) DEFAULT 'draft',
    subtotal        DECIMAL(12,2) DEFAULT 0,
    vat_amount      DECIMAL(12,2) DEFAULT 0,
    total_amount    DECIMAL(12,2) DEFAULT 0,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, po_number)
);
CREATE INDEX IF NOT EXISTS idx_po_client ON purchase_orders(client_id, status);

CREATE TABLE IF NOT EXISTS po_items (
    id              SERIAL PRIMARY KEY,
    po_id           INTEGER REFERENCES purchase_orders(id) ON DELETE CASCADE,
    item_id         INTEGER REFERENCES warehouse_items(id),
    item_name       VARCHAR(200) NOT NULL,
    quantity        DECIMAL(10,2) NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    total_price     DECIMAL(10,2) NOT NULL,
    received_qty    DECIMAL(10,2) DEFAULT 0
);

-- ──────────────────────────────────────────────────────────────
-- M14: الجولات السياحية — Tourism Tours
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tour_catalog (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    tour_code       VARCHAR(30) NOT NULL,
    name_ar         VARCHAR(200) NOT NULL,
    name_en         VARCHAR(200),
    description_ar  TEXT,
    tour_type       VARCHAR(30) DEFAULT 'city',
    duration_hours  DECIMAL(5,1),
    price_adult     DECIMAL(10,2) DEFAULT 0,
    price_child     DECIMAL(10,2) DEFAULT 0,
    max_capacity    INTEGER DEFAULT 10,
    includes_ar     TEXT,
    status          VARCHAR(20) DEFAULT 'active',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, tour_code)
);
CREATE INDEX IF NOT EXISTS idx_tour_client ON tour_catalog(client_id, status);

CREATE TABLE IF NOT EXISTS tour_bookings (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    tour_id         INTEGER REFERENCES tour_catalog(id),
    guest_id        INTEGER REFERENCES guests(id),
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    tour_date       DATE NOT NULL,
    tour_time       TIME,
    adults_count    INTEGER DEFAULT 1,
    children_count  INTEGER DEFAULT 0,
    guide_name      VARCHAR(100),
    total_price     DECIMAL(10,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tb_client_date ON tour_bookings(client_id, tour_date);

-- ──────────────────────────────────────────────────────────────
-- م14ب: وجهات سياحية — Tourist Destinations
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tourist_destinations (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    dest_code           VARCHAR(30) NOT NULL,
    name_ar             VARCHAR(200) NOT NULL,
    name_en             VARCHAR(200),
    description_ar      TEXT,
    city                VARCHAR(100),
    category            VARCHAR(50) DEFAULT 'heritage',
    latitude            DECIMAL(10,7),
    longitude           DECIMAL(10,7),
    entry_fee_adult     DECIMAL(10,2) DEFAULT 0,
    entry_fee_child     DECIMAL(10,2) DEFAULT 0,
    opening_hours       VARCHAR(200),
    website_url         TEXT,
    visit_duration_hours DECIMAL(5,1) DEFAULT 2,
    max_group_size      INTEGER DEFAULT 20,
    avg_rating          DECIMAL(3,2) DEFAULT 0,
    reviews_count       INTEGER DEFAULT 0,
    status              VARCHAR(20) DEFAULT 'active',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, dest_code)
);
CREATE INDEX IF NOT EXISTS idx_dest_client ON tourist_destinations(client_id, status);

CREATE TABLE IF NOT EXISTS destination_pois (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    destination_id  INTEGER REFERENCES tourist_destinations(id) ON DELETE CASCADE,
    name_ar         VARCHAR(200) NOT NULL,
    poi_type        VARCHAR(50) DEFAULT 'attraction',
    description_ar  TEXT,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS destination_bookings (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    destination_id  INTEGER REFERENCES tourist_destinations(id),
    guest_id        INTEGER REFERENCES guests(id),
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    visit_date      DATE NOT NULL,
    visit_time      TIME,
    adults_count    INTEGER DEFAULT 1,
    children_count  INTEGER DEFAULT 0,
    guide_required  BOOLEAN DEFAULT FALSE,
    guide_name      VARCHAR(100),
    total_price     DECIMAL(10,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'confirmed',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_db_client_date ON destination_bookings(client_id, visit_date);

CREATE TABLE IF NOT EXISTS destination_reviews (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    destination_id  INTEGER REFERENCES tourist_destinations(id) ON DELETE CASCADE,
    guest_id        INTEGER REFERENCES guests(id),
    rating          INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    review_text     TEXT,
    visit_date      DATE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rev_dest ON destination_reviews(destination_id);

-- ──────────────────────────────────────────────────────────────
-- نظام الإشعارات — Notifications
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    type            VARCHAR(30) DEFAULT 'info',
    title_ar        VARCHAR(200) NOT NULL,
    body_ar         TEXT,
    is_read         BOOLEAN DEFAULT FALSE,
    ref_type        VARCHAR(50),
    ref_id          VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_notif_client ON notifications(client_id, is_read, created_at DESC);

-- ──────────────────────────────────────────────────────────────
-- Triggers للوحدات الجديدة
-- ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
"""


# ── ترحيلات مُستخرَجة ─────────────────────────────────────────────
# نُقلت إلى db/schema_migrations.py ليبقى هذا الملف ضمن حدّ يُقرأ.
# تُعاد هنا لأن app_core يستوردها من `db.schema_v3` منذ البداية،
# وتغيير موضع الاستيراد بلا داعٍ يكسر ما لا يحتاج كسراً.
from db.schema_migrations import (  # noqa: E402,F401
    NEW_TRIGGERS,
    PERF_INDEXES,
    RLS_POLICIES,
    SESSIONS_MIGRATION,
    STAFF_ACCOUNTS_SCHEMA,
    STAFF_APP_ALTER,
    STAFF_APP_MIGRATIONS,
    run_perf_indexes,
    run_rls_migration,
    run_sessions_migration,
    run_staff_app_migrations,
)


def run_v3_migrations(db) -> None:
    import logging
    log = logging.getLogger("dheuof.db.migrations")
    log.info("🔄 تطبيق migrations v3 — جميع الوحدات الـ 15...")

    for statement in SCHEMA_V3_MODULES.split(";"):
        s = statement.strip()
        # تحقق: هل يوجد SQL حقيقي (سطر لا يبدأ بـ --)؟
        has_sql = any(
            line.strip() and not line.strip().startswith("--")
            for line in s.splitlines()
        )
        if s and has_sql:
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    log.error(f"خطأ v3: {e}\nSQL: {s[:80]}")

    for trigger_name, table_name in NEW_TRIGGERS:
        try:
            existing = db.execute(
                "SELECT 1 FROM information_schema.triggers WHERE trigger_name = %s",
                (trigger_name,), fetch="one"
            )
            if not existing:
                db.execute(f"""
                    CREATE TRIGGER {trigger_name}
                    BEFORE UPDATE ON {table_name}
                    FOR EACH ROW EXECUTE FUNCTION update_updated_at()
                """)
        except Exception as e:
            log.warning(f"Trigger {trigger_name}: {e}")

    log.info("✅ v3 migrations اكتملت")


# ── Security Hardening migrations (Isolation Audit — 10 findings) ──────────

def run_security_hardening(db) -> None:
    """
    تطبيق ملف SQL الأمني — specs/db/04-isolation-hardening.sql
    يعالج النقاط العشر من تقرير فحص أمن العزل.
    """
    import logging
    import os
    log = logging.getLogger("dheuof.db.security")

    if not db.use_postgres:
        log.info("⏭  Security hardening skipped — JSON fallback mode")
        return

    sql_path = os.path.join(os.path.dirname(__file__), "..", "specs", "db", "04-isolation-hardening.sql")
    sql_path = os.path.normpath(sql_path)

    if not os.path.exists(sql_path):
        log.warning(f"⚠️  Security hardening SQL not found: {sql_path}")
        return

    with open(sql_path, "r", encoding="utf-8") as f:
        raw_sql = f.read()

    # تقسيم على ';' مع تجاهل الـ DO $$ blocks بشكل صحيح
    statements = _split_sql_safe(raw_sql)
    ok = fail = 0
    for stmt in statements:
        s = stmt.strip()
        if not s or s.startswith("--"):
            continue
        try:
            db.execute(s)
            ok += 1
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ("already exists", "duplicate", "42p07", "42710")):
                ok += 1
            else:
                log.warning(f"hardening stmt failed: {e} | SQL: {s[:80]}")
                fail += 1

    # تشغيل audit على SECURITY DEFINER functions
    try:
        from db.security import audit_security_definer_functions
        funcs = audit_security_definer_functions(db)
        if funcs:
            log.warning(f"⚠️  SECURITY DEFINER functions detected ({len(funcs)}): "
                        f"{[f['function_name'] for f in funcs]}")
    except Exception as e:
        log.warning(f"SECURITY DEFINER audit: {e}")

    log.info(f"✅ Security hardening — {ok} statements OK, {fail} failed")


def _split_sql_safe(sql: str) -> list:
    """تقسيم SQL بشكل آمن مع الحفاظ على DO $$ ... $$ blocks."""
    statements = []
    current = []
    in_dollar_quote = False
    dollar_tag = ""

    for line in sql.splitlines():
        stripped = line.strip()
        if not in_dollar_quote:
            if "$$" in stripped:
                in_dollar_quote = True
                dollar_tag = "$$"
            if stripped.endswith(";") and not in_dollar_quote:
                current.append(line)
                statements.append("\n".join(current))
                current = []
                continue
        else:
            if dollar_tag in stripped and stripped != dollar_tag + ";":
                pass
            if stripped.endswith(dollar_tag + ";") or stripped == dollar_tag + ";":
                in_dollar_quote = False
                dollar_tag = ""
                current.append(line)
                statements.append("\n".join(current))
                current = []
                continue
        current.append(line)

    if current:
        leftover = "\n".join(current).strip()
        if leftover:
            statements.append(leftover)

    return statements


# ══════════════════════════════════════════════════════════════
#  v4 migrations — ZATCA + Night Audit + Reviews + Payments
# ══════════════════════════════════════════════════════════════

_SCHEMA_V4 = """
-- ──────────────────────────────────────────────────────────────
-- ZATCA — الفواتير الإلكترونية
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS zatca_invoices (
    id               SERIAL PRIMARY KEY,
    client_id        VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    invoice_number   VARCHAR(50) UNIQUE NOT NULL,
    booking_id       VARCHAR(100),
    guest_id         VARCHAR(100),
    invoice_type     VARCHAR(20)  DEFAULT 'SIMPLIFIED',
    issue_date       TIMESTAMPTZ  DEFAULT NOW(),
    supply_date      TIMESTAMPTZ  DEFAULT NOW(),
    subtotal         DECIMAL(12,2) DEFAULT 0,
    discount         DECIMAL(12,2) DEFAULT 0,
    vat_rate         DECIMAL(5,4)  DEFAULT 0.15,
    vat_amount       DECIMAL(12,2) DEFAULT 0,
    total            DECIMAL(12,2) DEFAULT 0,
    vat_number       VARCHAR(20),
    buyer_name       VARCHAR(200),
    buyer_vat        VARCHAR(20),
    zatca_uuid       VARCHAR(100),
    zatca_hash       VARCHAR(200),
    zatca_status     VARCHAR(20)  DEFAULT 'PENDING',
    qr_tlv_base64    TEXT,
    qr_image_base64  TEXT,
    xml_signed       TEXT,
    pdf_url          VARCHAR(500),
    is_deleted       BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_zatca_client ON zatca_invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_zatca_booking ON zatca_invoices(booking_id);
CREATE INDEX IF NOT EXISTS idx_zatca_status ON zatca_invoices(zatca_status);

-- ──────────────────────────────────────────────────────────────
-- Night Audit — إعدادات وسجل الإغلاق اليومي
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS night_audit_settings (
    id                      SERIAL PRIMARY KEY,
    client_id               VARCHAR(50) UNIQUE REFERENCES clients(id) ON DELETE CASCADE,
    auto_run                BOOLEAN DEFAULT FALSE,
    scheduled_time          VARCHAR(5)  DEFAULT '23:59',
    default_check_in_time   VARCHAR(5)  DEFAULT '14:00',
    default_check_out_time  VARCHAR(5)  DEFAULT '12:00',
    grace_period_minutes    INTEGER DEFAULT 30,
    require_payment_close   BOOLEAN DEFAULT TRUE,
    updated_by              VARCHAR(100),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS night_audit_log (
    id                  SERIAL PRIMARY KEY,
    client_id           VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    audit_date          DATE NOT NULL,
    status              VARCHAR(20)  DEFAULT 'PENDING',
    trigger_type        VARCHAR(20)  DEFAULT 'MANUAL',
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    performed_by        VARCHAR(100),
    rooms_audited       INTEGER DEFAULT 0,
    payments_verified   INTEGER DEFAULT 0,
    unsettled_payments  INTEGER DEFAULT 0,
    total_revenue       DECIMAL(12,2) DEFAULT 0,
    errors_count        INTEGER DEFAULT 0,
    report_data         JSONB DEFAULT '{}',
    notes               TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_log_client ON night_audit_log(client_id, audit_date);

-- ──────────────────────────────────────────────────────────────
-- أجهزة الدفع
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS payment_devices (
    id               SERIAL PRIMARY KEY,
    client_id        VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    device_name      VARCHAR(100) NOT NULL,
    device_type      VARCHAR(30)  DEFAULT 'POS',
    serial_number    VARCHAR(100),
    is_active        BOOLEAN DEFAULT TRUE,
    last_settled_at  TIMESTAMPTZ,
    daily_total      DECIMAL(12,2) DEFAULT 0,
    is_deleted       BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_devices_client ON payment_devices(client_id);

-- ──────────────────────────────────────────────────────────────
-- تقييمات الحجوزات
-- ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS booking_reviews (
    id               SERIAL PRIMARY KEY,
    client_id        VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id       VARCHAR(100) NOT NULL,
    guest_id         VARCHAR(100),
    recorded_by      VARCHAR(100),
    overall_rating   SMALLINT CHECK (overall_rating BETWEEN 1 AND 5),
    cleanliness      SMALLINT CHECK (cleanliness    BETWEEN 1 AND 5),
    service          SMALLINT CHECK (service        BETWEEN 1 AND 5),
    location         SMALLINT CHECK (location       BETWEEN 1 AND 5),
    value_for_money  SMALLINT CHECK (value_for_money BETWEEN 1 AND 5),
    comment          TEXT,
    is_public        BOOLEAN DEFAULT TRUE,
    management_reply TEXT,
    replied_by       VARCHAR(100),
    replied_at       TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, booking_id)
);
CREATE INDEX IF NOT EXISTS idx_reviews_client ON booking_reviews(client_id);
"""


def run_v4_migrations(db) -> None:
    """تشغيل migrations الوحدات الجديدة — ZATCA + Night Audit + Reviews"""
    import logging
    log = logging.getLogger("dheuof.db.migrations")
    if not db.use_postgres:
        log.info("v4 migrations: JSON mode — skip")
        return
    ok = fail = 0
    for s in _split_sql_safe(_SCHEMA_V4):
        s = s.strip()
        if not s:
            continue
        try:
            db.execute(s)
            ok += 1
        except Exception as e:
            err = str(e).lower()
            if any(x in err for x in ("already exists", "duplicate", "42p07", "42710")):
                ok += 1
            else:
                log.warning(f"v4 migration failed: {e} | SQL: {s[:80]}")
                fail += 1
    log.info(f"✅ v4 migrations — {ok} OK, {fail} failed")

    # ── ضريبة السياحة (Tourism Tax 2.5%) — أعمدة zatca_invoices ─
    _tourism_cols = [
        "tourism_tax_rate   DECIMAL(5,4) DEFAULT 0.025",
        "tourism_tax_amount DECIMAL(12,2) DEFAULT 0",
        "tax_absorbed_by    VARCHAR(20)   DEFAULT 'guest'",
    ]
    for col_def in _tourism_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE zatca_invoices ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"tourism tax col {col_name}: {e}")

    # ── أعمدة الضريبة المركزية — bookings ────────────────────────
    _booking_tax_cols = [
        "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
        "vat_amount          DECIMAL(12,2) DEFAULT 0",
        "tourism_tax_amount  DECIMAL(12,2) DEFAULT 0",
    ]
    for col_def in _booking_tax_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE bookings ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"bookings tax col {col_name}: {e}")

    # ── أعمدة الضريبة المركزية — pos_sales ───────────────────────
    _pos_tax_cols = [
        "subtotal            DECIMAL(10,2) DEFAULT 0",
        "vat_amount          DECIMAL(10,2) DEFAULT 0",
        "tourism_tax_amount  DECIMAL(10,2) DEFAULT 0",
        "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
    ]
    for col_def in _pos_tax_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE pos_sales ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"pos_sales tax col {col_name}: {e}")

    # ── أعمدة الضريبة المركزية — purchase_orders ─────────────────
    _po_tax_cols = [
        "vat_amount          DECIMAL(12,2) DEFAULT 0",
        "tourism_tax_amount  DECIMAL(12,2) DEFAULT 0",
        "tax_mode            VARCHAR(10)   DEFAULT 'MODE_A'",
    ]
    for col_def in _po_tax_cols:
        col_name = col_def.split()[0]
        try:
            db.execute(
                f"ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"purchase_orders tax col {col_name}: {e}")

    # ── جدول القيود المحاسبية (API مفتوح) ────────────────────────
    try:
        db.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id          SERIAL PRIMARY KEY,
                client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
                reference   VARCHAR(100),
                entry_date  DATE DEFAULT CURRENT_DATE,
                description TEXT,
                lines       JSONB DEFAULT '[]',
                source      VARCHAR(30) DEFAULT 'external',
                created_at  TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"journal_entries table: {e}")

    # ── مفتاح API للربط بالأنظمة الخارجية (clients.api_key) ─────
    try:
        db.execute(
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS api_key VARCHAR(80) UNIQUE"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"clients.api_key col: {e}")

    # ── ربط الدفعة بجهاز نقطة البيع (payments.device_id) ─────────
    try:
        db.execute(
            "ALTER TABLE payments ADD COLUMN IF NOT EXISTS device_id INTEGER"
        )
    except Exception as e:
        if "already exists" not in str(e).lower():
            log.warning(f"payments.device_id col: {e}")

    # ── موقع تذكرة الصيانة وتقريرها ─────────────────────────────
    # location_type: room|corridor|outside|floor (غرفة/ممر/خارج/دور)
    for col_def in (
        "location_type VARCHAR(20)",
        "location_label VARCHAR(120)",
        "report TEXT",
    ):
        try:
            db.execute(
                f"ALTER TABLE maintenance_orders ADD COLUMN IF NOT EXISTS {col_def}"
            )
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"maintenance_orders.{col_def}: {e}")
