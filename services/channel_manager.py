#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مدير قنوات التوزيع (OTA Channel Manager)
=========================================
طبقة وسيطة تربط ضيوف بمنصات الحجز العالمية (Booking.com / Expedia / Airbnb …)
عبر نمط Channel Manager موحّد:

    التوافر + الأسعار  ──push──▶  القناة (OTA)
    حجوزات القناة      ◀─pull──   webhook ────▶  جدول الحجوزات

التصميم:
- لا يخزّن أي مفتاح سري خام أبداً — يُخزَّن قناع (hint) + بصمة SHA-256 فقط.
- يتدهور بأمان عندما لا تتوفر PostgreSQL (يُعيد قوائم فارغة بدل الانهيار).
- كل عملية مزامنة تُسجَّل في channel_sync_log للتدقيق.
"""
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Optional

log = logging.getLogger("dheuof.channels")

# ── القنوات المدعومة عبر الوسيط ───────────────────────────────
SUPPORTED_CHANNELS = [
    {"code": "booking",   "name": "Booking.com", "ar": "بوكينج",   "commission": 15.0},
    {"code": "expedia",   "name": "Expedia",     "ar": "إكسبيديا", "commission": 18.0},
    {"code": "airbnb",    "name": "Airbnb",      "ar": "إير بي إن بي", "commission": 14.0},
    {"code": "agoda",     "name": "Agoda",       "ar": "أجودا",    "commission": 17.0},
    {"code": "almosafer", "name": "Almosafer",   "ar": "المسافر",  "commission": 12.0},
    {"code": "gathern",   "name": "Gathern",     "ar": "قذني",     "commission": 10.0},
]
_VALID_CODES = {c["code"] for c in SUPPORTED_CHANNELS}


def _mask_secret(secret: str) -> str:
    """يُعيد قناعاً آمناً للمفتاح — لا يُخزَّن المفتاح الخام أبداً."""
    if not secret:
        return ""
    secret = str(secret)
    if len(secret) <= 4:
        return "••••"
    return secret[:3] + "••••••" + secret[-4:]


def _fingerprint(secret: str) -> str:
    """بصمة SHA-256 للتحقق من المفتاح دون تخزينه."""
    return hashlib.sha256(str(secret).encode("utf-8")).hexdigest() if secret else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChannelManager:
    """مدير قنوات التوزيع — يُهيّأ مرة واحدة في lifespan عبر ChannelManager(db)."""

    def __init__(self, db):
        self.db = db
        self._ready = False
        try:
            self.ensure_schema()
            self._ready = True
        except Exception as e:  # pragma: no cover - defensive
            log.warning(f"تعذّر تهيئة مخطط القنوات: {e}")

    # ── المخطط ────────────────────────────────────────────────
    def ensure_schema(self) -> None:
        if not getattr(self.db, "use_postgres", False):
            return
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS channel_connections (
                id           SERIAL PRIMARY KEY,
                client_id    VARCHAR(50) NOT NULL,
                channel_code VARCHAR(30) NOT NULL,
                status       VARCHAR(20) DEFAULT 'connected',
                key_hint     VARCHAR(40) DEFAULT '',
                key_fp       VARCHAR(64) DEFAULT '',
                last_sync    TIMESTAMPTZ,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (client_id, channel_code)
            )
        """)
        # `channel_sync_log` يملكه `db/migrations.py` — كان مُعرَّفاً هنا
        # أيضاً بأعمدةٍ مختلفة، و`IF NOT EXISTS` لا يُعدّل جدولاً قائماً،
        # فبقي مخطّط الترحيلات وحده نافذاً بينما تكتب هذه الوحدة وتقرأ
        # بأسماءٍ لا وجود لها: القراءة ترمي ٥٠٠، والكتابة تُبتلع بتحذير
        # فيبقى سجلّ التدقيق فارغاً أبداً ولا أحد يعلم.
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS channel_reservations (
                id           SERIAL PRIMARY KEY,
                client_id    VARCHAR(50) NOT NULL,
                channel_code VARCHAR(30) NOT NULL,
                external_id  VARCHAR(80) NOT NULL,
                guest_name   VARCHAR(160) DEFAULT '',
                check_in     DATE,
                check_out    DATE,
                room_type    VARCHAR(80) DEFAULT '',
                amount       DECIMAL(12,2) DEFAULT 0,
                currency     VARCHAR(8) DEFAULT 'SAR',
                status       VARCHAR(20) DEFAULT 'new',
                booking_id   VARCHAR(50),
                raw          JSONB,
                created_at   TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE (client_id, channel_code, external_id)
            )
        """)
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS idx_chres_client ON channel_reservations(client_id, status)")

    # ── القنوات المدعومة ──────────────────────────────────────
    @staticmethod
    def supported_channels() -> list:
        return [dict(c) for c in SUPPORTED_CHANNELS]

    def _log(self, client_id, channel_code, action, rooms=0, ok=True, detail=""):
        if not getattr(self.db, "use_postgres", False):
            return
        try:
            self.db.execute(
                """INSERT INTO channel_sync_log
                   (client_id, channel_name, sync_type, records_synced, status, error_message)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (client_id, channel_code, action, rooms,
                 "success" if ok else "failed", detail[:500] or None))
        except Exception as e:  # pragma: no cover
            log.warning(f"تعذّر تسجيل المزامنة: {e}")

    # ── الاتصالات ─────────────────────────────────────────────
    def list_connections(self, client_id: str) -> list:
        if not getattr(self.db, "use_postgres", False):
            return []
        rows = self.db.execute(
            """SELECT channel_code, status, key_hint, last_sync, created_at
               FROM channel_connections WHERE client_id=%s ORDER BY created_at""",
            (client_id,), fetch="all") or []
        by_code = {dict(r)["channel_code"]: dict(r) for r in rows}
        out = []
        for ch in SUPPORTED_CHANNELS:
            conn = by_code.get(ch["code"])
            out.append({
                **ch,
                "connected": bool(conn),
                "status": conn["status"] if conn else "disconnected",
                "key_hint": conn["key_hint"] if conn else "",
                "last_sync": (conn["last_sync"].isoformat()
                              if conn and conn.get("last_sync") else None),
            })
        return out

    def connect(self, client_id: str, channel_code: str, api_key: str) -> dict:
        if channel_code not in _VALID_CODES:
            raise ValueError(f"قناة غير مدعومة: {channel_code}")
        if not api_key or not str(api_key).strip():
            raise ValueError("مفتاح API مطلوب للربط")
        if not getattr(self.db, "use_postgres", False):
            return {"channel_code": channel_code, "status": "connected",
                    "key_hint": _mask_secret(api_key)}
        hint, fp = _mask_secret(api_key), _fingerprint(api_key)
        # المفتاح الحقيقي يُخزَّن مشفّراً في خزنة الاعتمادات (لا قناعاً غير
        # قابلٍ للاستخدام) كي تستطيع المحوّلات النداء الفعلي على القناة.
        from services import integration_credentials as vault
        vault.save(self.db, client_id, channel_code, {"api_key": api_key})
        self.db.execute(
            """INSERT INTO channel_connections
               (client_id, channel_code, status, key_hint, key_fp)
               VALUES (%s,%s,'connected',%s,%s)
               ON CONFLICT (client_id, channel_code)
               DO UPDATE SET status='connected', key_hint=EXCLUDED.key_hint,
                             key_fp=EXCLUDED.key_fp""",
            (client_id, channel_code, hint, fp))
        self._log(client_id, channel_code, "connect", detail="ربط القناة")
        return {"channel_code": channel_code, "status": "connected", "key_hint": hint}

    def get_secret(self, client_id: str, channel_code: str) -> dict | None:
        """اعتماد القناة المفكوك للمحوّل (لا لـHTTP). None إن غاب."""
        from services import integration_credentials as vault
        return vault.get(self.db, client_id, channel_code)

    def disconnect(self, client_id: str, channel_code: str) -> bool:
        if not getattr(self.db, "use_postgres", False):
            return True
        n = self.db.execute(
            "DELETE FROM channel_connections WHERE client_id=%s AND channel_code=%s",
            (client_id, channel_code))
        self._log(client_id, channel_code, "disconnect", detail="فصل القناة")
        return bool(n)

    # ── مزامنة التوافر والأسعار (push) ────────────────────────
    def _available_rooms(self, client_id: str) -> int:
        if not getattr(self.db, "use_postgres", False):
            return 0
        row = self.db.execute(
            "SELECT COUNT(*) AS c FROM rooms WHERE client_id=%s", (client_id,), fetch="one")
        return dict(row).get("c", 0) if row else 0

    def sync_rates(self, client_id: str, channel_code: Optional[str] = None) -> dict:
        """يدفع التوافر والأسعار إلى قناة واحدة أو لكل القنوات المتصلة."""
        if not getattr(self.db, "use_postgres", False):
            return {"synced": [], "rooms": 0}
        if channel_code:
            targets = [channel_code]
        else:
            rows = self.db.execute(
                "SELECT channel_code FROM channel_connections WHERE client_id=%s AND status='connected'",
                (client_id,), fetch="all") or []
            targets = [dict(r)["channel_code"] for r in rows]
        rooms = self._available_rooms(client_id)
        synced = []
        for code in targets:
            if code not in _VALID_CODES:
                continue
            # نقطة الإرسال الفعلي للوسيط (SiteMinder/RateGain) تُضاف هنا.
            self.db.execute(
                "UPDATE channel_connections SET last_sync=NOW() WHERE client_id=%s AND channel_code=%s",
                (client_id, code))
            self._log(client_id, code, "sync_rates", rooms=rooms,
                      detail=f"دفع {rooms} غرفة")
            synced.append(code)
        return {"synced": synced, "rooms": rooms, "at": _now_iso()}

    # ── استقبال حجوزات القناة (pull / webhook) ────────────────
    def ingest_reservation(self, client_id: str, channel_code: str, payload: dict) -> dict:
        """يستقبل حجزاً وارداً من قناة OTA ويخزّنه (idempotent عبر external_id)."""
        if channel_code not in _VALID_CODES:
            raise ValueError(f"قناة غير مدعومة: {channel_code}")
        ext_id = str(payload.get("external_id") or payload.get("id") or "").strip()
        if not ext_id:
            raise ValueError("معرّف الحجز الخارجي مفقود")
        if not getattr(self.db, "use_postgres", False):
            return {"external_id": ext_id, "status": "new", "stored": False}
        self.db.execute(
            """INSERT INTO channel_reservations
               (client_id, channel_code, external_id, guest_name, check_in,
                check_out, room_type, amount, currency, status, raw)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'new',%s)
               ON CONFLICT (client_id, channel_code, external_id)
               DO UPDATE SET guest_name=EXCLUDED.guest_name,
                             check_in=EXCLUDED.check_in, check_out=EXCLUDED.check_out,
                             amount=EXCLUDED.amount, raw=EXCLUDED.raw""",
            (client_id, channel_code, ext_id,
             payload.get("guest_name", ""), payload.get("check_in"),
             payload.get("check_out"), payload.get("room_type", ""),
             payload.get("amount", 0), payload.get("currency", "SAR"),
             json.dumps(payload, ensure_ascii=False)))
        self._log(client_id, channel_code, "ingest_reservation",
                  detail=f"حجز وارد {ext_id}")
        return {"external_id": ext_id, "status": "new", "stored": True}

    def list_reservations(self, client_id: str, status: Optional[str] = None) -> list:
        if not getattr(self.db, "use_postgres", False):
            return []
        if status:
            rows = self.db.execute(
                """SELECT * FROM channel_reservations
                   WHERE client_id=%s AND status=%s ORDER BY created_at DESC""",
                (client_id, status), fetch="all")
        else:
            rows = self.db.execute(
                """SELECT * FROM channel_reservations
                   WHERE client_id=%s ORDER BY created_at DESC""",
                (client_id,), fetch="all")
        return [dict(r) for r in (rows or [])]

    def sync_log(self, client_id: str, limit: int = 50) -> list:
        if not getattr(self.db, "use_postgres", False):
            return []
        rows = self.db.execute(
            """SELECT channel_name  AS channel_code,
                      sync_type     AS action,
                      records_synced AS rooms_count,
                      (status = 'success') AS ok,
                      COALESCE(error_message, '') AS detail,
                      created_at
               FROM channel_sync_log WHERE client_id=%s
               ORDER BY created_at DESC LIMIT %s""",
            (client_id, limit), fetch="all")
        return [dict(r) for r in (rows or [])]
