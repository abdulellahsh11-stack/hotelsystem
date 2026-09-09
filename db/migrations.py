#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/migrations.py — Schema كامل لنظام ضيوف
آمن للتشغيل أكثر من مرة (idempotent) بفضل IF NOT EXISTS
"""
import logging

log = logging.getLogger("dheuof.db.migrations")


# ── Schema SQL ────────────────────────────────────────────────
_SCHEMA_V1 = """
-- ================================================================
-- DHEUOF Database Schema v2.0 — الشهر الثاني
-- ================================================================

-- المنشآت (العملاء)
CREATE TABLE IF NOT EXISTS clients (
    id              VARCHAR(50) PRIMARY KEY,
    name            VARCHAR(200) NOT NULL,
    type            VARCHAR(50),
    city            VARCHAR(100),
    region          VARCHAR(100),
    phone           VARCHAR(20),
    email           VARCHAR(200),
    units_count     INTEGER DEFAULT 0,
    settings_locked BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    settings         JSONB DEFAULT '{}',
    whatsapp_config  JSONB DEFAULT '{}',
    chatbot_config   JSONB DEFAULT '{}',
    invoice_settings JSONB DEFAULT '{}',
    review_settings  JSONB DEFAULT '{}'
);

-- الاشتراكات
CREATE TABLE IF NOT EXISTS subscriptions (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    plan        VARCHAR(50),
    status      VARCHAR(30) DEFAULT 'trial',
    trial_end   DATE,
    sub_start   DATE,
    sub_end     DATE,
    price       DECIMAL(10,2) DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sub_client ON subscriptions(client_id);

-- مفاتيح الترخيص
CREATE TABLE IF NOT EXISTS license_keys (
    key         VARCHAR(100) PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE SET NULL,
    plan        VARCHAR(50),
    expires_at  DATE,
    used        BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- الغرف
CREATE TABLE IF NOT EXISTS rooms (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_number VARCHAR(20) NOT NULL,
    room_type   VARCHAR(100),
    floor       INTEGER,
    capacity    INTEGER DEFAULT 2,
    base_price  DECIMAL(10,2) DEFAULT 0,
    status      VARCHAR(30) DEFAULT 'available',
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, room_number)
);
CREATE INDEX IF NOT EXISTS idx_rooms_client_status ON rooms(client_id, status);

-- النزلاء
CREATE TABLE IF NOT EXISTS guests (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    id_type     VARCHAR(20),
    id_number   VARCHAR(20),
    full_name   VARCHAR(200) NOT NULL,
    absher_phone VARCHAR(20),
    nationality VARCHAR(100),
    birth_date  DATE,
    data_status VARCHAR(20) DEFAULT 'incomplete',
    source      VARCHAR(50),
    notes       TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_guests_client     ON guests(client_id);
CREATE INDEX IF NOT EXISTS idx_guests_id_number  ON guests(id_type, id_number);

-- الحجوزات
CREATE TABLE IF NOT EXISTS bookings (
    id                      VARCHAR(50) PRIMARY KEY,
    client_id               VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id                INTEGER REFERENCES guests(id),
    room_id                 INTEGER REFERENCES rooms(id),
    check_in                DATE NOT NULL,
    check_out               DATE NOT NULL,
    actual_check_in         TIMESTAMPTZ,
    actual_check_out        TIMESTAMPTZ,
    nightly_rate            DECIMAL(10,2),
    total_room              DECIMAL(10,2),
    status                  VARCHAR(30) DEFAULT 'confirmed',
    source                  VARCHAR(50),
    company_name            VARCHAR(200),
    pre_arrival_token       VARCHAR(100) UNIQUE,
    pre_arrival_status      VARCHAR(20) DEFAULT 'pending',
    pre_arrival_data        JSONB DEFAULT '{}',
    companions              JSONB DEFAULT '[]',
    wa_confirmation_sent    BOOLEAN DEFAULT FALSE,
    wa_pre_arrival_sent     BOOLEAN DEFAULT FALSE,
    wa_arrival_sent         BOOLEAN DEFAULT FALSE,
    wa_mid_stay_sent        BOOLEAN DEFAULT FALSE,
    wa_checkout_sent        BOOLEAN DEFAULT FALSE,
    wa_review_sent          BOOLEAN DEFAULT FALSE,
    wa_review_scheduled_at  TIMESTAMPTZ,
    notes                   TEXT,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bookings_client      ON bookings(client_id);
CREATE INDEX IF NOT EXISTS idx_bookings_dates       ON bookings(client_id, check_in, check_out);
CREATE INDEX IF NOT EXISTS idx_bookings_status      ON bookings(client_id, status);
CREATE INDEX IF NOT EXISTS idx_bookings_pre_arrival ON bookings(pre_arrival_token);

-- عمليات POS
CREATE TABLE IF NOT EXISTS pos_transactions (
    id             SERIAL PRIMARY KEY,
    client_id      VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id     VARCHAR(50) REFERENCES bookings(id),
    date           DATE NOT NULL DEFAULT CURRENT_DATE,
    payment_method VARCHAR(30),
    amount         DECIMAL(10,2) NOT NULL,
    vat_amount     DECIMAL(10,2),
    net_amount     DECIMAL(10,2),
    category       VARCHAR(100),
    description    TEXT,
    cashier        VARCHAR(100),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pos_client_date ON pos_transactions(client_id, date);
CREATE INDEX IF NOT EXISTS idx_pos_booking     ON pos_transactions(booking_id);

-- المستودعات
CREATE TABLE IF NOT EXISTS warehouse_items (
    id                 SERIAL PRIMARY KEY,
    client_id          VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    warehouse_type     VARCHAR(20),
    name               VARCHAR(200) NOT NULL,
    unit               VARCHAR(20),
    quantity           DECIMAL(10,2) DEFAULT 0,
    reorder_level      DECIMAL(10,2) DEFAULT 0,
    price_per_unit     DECIMAL(10,2) DEFAULT 0,
    per_room_per_night DECIMAL(10,2) DEFAULT 0,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_warehouse_client ON warehouse_items(client_id, warehouse_type);

-- حركات المستودع
CREATE TABLE IF NOT EXISTS warehouse_movements (
    id            SERIAL PRIMARY KEY,
    item_id       INTEGER REFERENCES warehouse_items(id) ON DELETE CASCADE,
    client_id     VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    movement_type VARCHAR(20),
    quantity      DECIMAL(10,2) NOT NULL,
    booking_id    VARCHAR(50) REFERENCES bookings(id),
    notes         TEXT,
    created_by    VARCHAR(100),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_movements_item        ON warehouse_movements(item_id);
CREATE INDEX IF NOT EXISTS idx_movements_client_date ON warehouse_movements(client_id, created_at);

-- الفواتير
CREATE TABLE IF NOT EXISTS invoices (
    id              VARCHAR(50) PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id      VARCHAR(50) REFERENCES bookings(id),
    guest_id        INTEGER REFERENCES guests(id),
    issue_date      DATE DEFAULT CURRENT_DATE,
    subtotal        DECIMAL(10,2) NOT NULL,
    vat_amount      DECIMAL(10,2) NOT NULL,
    total_amount    DECIMAL(10,2) NOT NULL,
    payment_method  VARCHAR(30),
    payment_status  VARCHAR(20) DEFAULT 'paid',
    line_items      JSONB DEFAULT '[]',
    whatsapp_sent   BOOLEAN DEFAULT FALSE,
    whatsapp_sent_at TIMESTAMPTZ,
    pdf_generated   BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id);
CREATE INDEX IF NOT EXISTS idx_invoices_date   ON invoices(client_id, issue_date);

-- مصادر iCal
CREATE TABLE IF NOT EXISTS ical_sources (
    id           SERIAL PRIMARY KEY,
    client_id    VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    name         VARCHAR(100),
    url          TEXT NOT NULL,
    last_sync    TIMESTAMPTZ,
    events_count INTEGER DEFAULT 0,
    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- تعارضات iCal
CREATE TABLE IF NOT EXISTS ical_conflicts (
    id             SERIAL PRIMARY KEY,
    client_id      VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id     VARCHAR(50) REFERENCES bookings(id),
    ical_source_id INTEGER REFERENCES ical_sources(id),
    external_event JSONB,
    detected_at    TIMESTAMPTZ DEFAULT NOW(),
    resolved       BOOLEAN DEFAULT FALSE
);

-- سجل واتساب
CREATE TABLE IF NOT EXISTS whatsapp_log (
    id           SERIAL PRIMARY KEY,
    client_id    VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    booking_id   VARCHAR(50) REFERENCES bookings(id),
    guest_phone  VARCHAR(20),
    message_type VARCHAR(50),
    status       VARCHAR(20),
    error_message TEXT,
    sent_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_wa_log_client ON whatsapp_log(client_id, sent_at);

-- محادثات chatbot
CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_phone VARCHAR(20) NOT NULL,
    role        VARCHAR(10) NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chatbot_phone ON chatbot_conversations(client_id, guest_phone, created_at);

-- تصعيد المحادثات
CREATE TABLE IF NOT EXISTS escalation_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_phone     VARCHAR(20),
    trigger_message TEXT,
    summary         TEXT,
    handled         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- أحداث المفاتيح الإلكترونية
CREATE TABLE IF NOT EXISTS key_events (
    id           SERIAL PRIMARY KEY,
    client_id    VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    room_id      INTEGER REFERENCES rooms(id),
    event_type   VARCHAR(50),
    employee_name VARCHAR(100),
    is_suspicious BOOLEAN DEFAULT FALSE,
    raw_data     JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_keys_client_date ON key_events(client_id, created_at);

-- تتابع أرقام الفواتير
CREATE TABLE IF NOT EXISTS sequences (
    client_id   VARCHAR(50) PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
    invoice_seq INTEGER DEFAULT 0
);

-- تذاكر الدعم
CREATE TABLE IF NOT EXISTS tickets (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    subject     VARCHAR(300),
    body        TEXT,
    status      VARCHAR(20) DEFAULT 'open',
    priority    VARCHAR(20) DEFAULT 'normal',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- سجل المدفوعات (للمالك)
CREATE TABLE IF NOT EXISTS payments (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    amount      DECIMAL(10,2) NOT NULL,
    currency    VARCHAR(10) DEFAULT 'SAR',
    method      VARCHAR(50),
    reference   VARCHAR(100),
    device_id   INTEGER,
    period_from DATE,
    period_to   DATE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- سجلّ أحداث بوابة الدفع (ميسر) — كل حدث ويب هوك يُسجَّل هنا.
-- dedup_key فريدٌ فيمنع معالجة الحدث مرّتين (لا رسوم مكرّرة، إيديمبوتنسي).
-- client_id قد يكون NULL لحدثٍ رُفض توقيعه (لا نثق بحمولته لننسبه لمنشأة).
CREATE TABLE IF NOT EXISTS payment_events (
    id          SERIAL PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    dedup_key   VARCHAR(160) UNIQUE,
    event_type  VARCHAR(50),
    payment_id  VARCHAR(120),
    amount      DECIMAL(12,2),
    currency    VARCHAR(10) DEFAULT 'SAR',
    status      VARCHAR(30),
    raw         JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_pe_client  ON payment_events(client_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pe_payment ON payment_events(payment_id);

-- ================================================================
-- جداول الأمان — Security Tables (Isolation Audit)
-- ================================================================

-- Finding #8: إبطال الجلسات الفوري
CREATE TABLE IF NOT EXISTS revoked_sessions (
    token_hash  VARCHAR(128) PRIMARY KEY,
    client_id   VARCHAR(50),
    revoked_at  TIMESTAMPTZ DEFAULT NOW(),
    reason      VARCHAR(100) DEFAULT 'logout'
);
CREATE INDEX IF NOT EXISTS idx_revoked_client ON revoked_sessions(client_id);

-- Finding #4: جلسات الضيوف المعزولة
CREATE TABLE IF NOT EXISTS guest_sessions (
    token_hash  VARCHAR(128) PRIMARY KEY,
    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    guest_id    INTEGER REFERENCES guests(id) ON DELETE CASCADE,
    booking_id  VARCHAR(50) REFERENCES bookings(id) ON DELETE CASCADE,
    actor_type  VARCHAR(20) DEFAULT 'guest',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours'
);
CREATE INDEX IF NOT EXISTS idx_gs_expires ON guest_sessions(expires_at);

-- ================================================================
-- نظام المسوقين — Affiliate Marketing
-- ================================================================

-- جدول المسوقين
CREATE TABLE IF NOT EXISTS marketers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    phone           VARCHAR(30),
    email           VARCHAR(150),
    ref_code        VARCHAR(30) UNIQUE NOT NULL,
    commission_rate DECIMAL(5,2) DEFAULT 10.0,
    total_earnings  DECIMAL(12,2) DEFAULT 0,
    status          VARCHAR(20) DEFAULT 'active',
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_mktr_code ON marketers(ref_code, status);

-- جدول التسجيلات من رابط المسوق
CREATE TABLE IF NOT EXISTS marketer_referrals (
    id              SERIAL PRIMARY KEY,
    marketer_id     INTEGER REFERENCES marketers(id) ON DELETE CASCADE,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    plan            VARCHAR(50),
    ref_code        VARCHAR(30),
    converted_at    TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id)
);
CREATE INDEX IF NOT EXISTS idx_ref_marketer ON marketer_referrals(marketer_id);

-- إعدادات القنوات (Booking.com, Mawasim, etc.)
CREATE TABLE IF NOT EXISTS channel_configs (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    channel_name    VARCHAR(50) NOT NULL,
    credentials     JSONB DEFAULT '{}',
    is_enabled      BOOLEAN DEFAULT TRUE,
    last_sync_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(client_id, channel_name)
);
CREATE INDEX IF NOT EXISTS idx_chan_cfg_client ON channel_configs(client_id);

-- سجل مزامنة القنوات
CREATE TABLE IF NOT EXISTS channel_sync_log (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
    channel_name    VARCHAR(50),
    sync_type       VARCHAR(50),
    status          VARCHAR(20) DEFAULT 'success',
    records_synced  INTEGER DEFAULT 0,
    error_message   TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_chan_log_client ON channel_sync_log(client_id, created_at DESC);

-- ================================================================
-- TRIGGERS — تحديث updated_at تلقائياً
-- ================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
"""

_TRIGGERS = [
    ("trg_clients_updated",   "clients"),
    ("trg_guests_updated",    "guests"),
    ("trg_bookings_updated",  "bookings"),
    ("trg_warehouse_updated", "warehouse_items"),
    ("trg_tickets_updated",   "tickets"),
]


def run_all_migrations(db) -> None:
    """
    تطبيق كل الـ migrations — آمن للتشغيل أكثر من مرة.
    db: DatabasePool instance
    """
    log.info("🔄 بدء تطبيق database migrations...")

    try:
        # 1. إنشاء الجداول — نفصل دالة dollar-quoted عن بقية الـ schema
        _schema_tables = _SCHEMA_V1[:_SCHEMA_V1.find("CREATE OR REPLACE FUNCTION")]

        for statement in _schema_tables.split(";"):
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
                        log.error(f"خطأ في migration statement: {e}\nSQL: {s[:100]}")

        # 1b. إنشاء دالة updated_at بشكل منفصل (تجنب مشكلة dollar-quote split)
        try:
            db.execute("""
                CREATE OR REPLACE FUNCTION update_updated_at()
                RETURNS TRIGGER AS $$
                BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
                $$ LANGUAGE plpgsql
            """)
        except Exception as e:
            if "already exists" not in str(e).lower():
                log.warning(f"⚠️ دالة update_updated_at: {e}")

        # 2. إنشاء الـ triggers (IF NOT EXISTS لا يدعمها PostgreSQL للـ triggers)
        for trigger_name, table_name in _TRIGGERS:
            try:
                # تحقق إذا الـ trigger موجود
                existing = db.execute(
                    "SELECT 1 FROM information_schema.triggers WHERE trigger_name = %s",
                    (trigger_name,),
                    fetch="one",
                )
                if not existing:
                    db.execute(f"""
                        CREATE TRIGGER {trigger_name}
                        BEFORE UPDATE ON {table_name}
                        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
                    """)
                    log.info(f"  ✓ Trigger {trigger_name} created")
            except Exception as e:
                log.warning(f"  ⚠️ Trigger {trigger_name}: {e}")

        log.info("✅ Database migrations اكتملت بنجاح")

    except Exception as e:
        log.error(f"❌ فشل في migrations: {e}")
        raise
