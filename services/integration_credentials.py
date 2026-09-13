#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/integration_credentials.py — خزنة اعتمادات التكاملات لكل مشترك.

تحلّ مشاكل مراجعة التكاملات: **لكل مشترك اعتماده الخاص، مشفّراً، تحت تصرّفه،
مقنّعاً للعرض، ولا يُقرأ من بيئةٍ مركزية ولا يُخزَّن قناعاً غير قابلٍ للاستخدام
ولا يخرج خاماً عبر HTTP.**

- التخزين: JSON الاعتماد مشفّرٌ AES-256-GCM عبر `services.guest_crypto`.
  بلا تشفيرٍ مُفعَّل (تطوير) لا يُحفَظ سرٌّ حقيقي — لا سقوط إلى نصٍّ صريح.
- الاسترجاع للاستخدام (`get`) يفكّ التشفير — للمحوّلات لا لـHTTP.
- العرض (`status`) يُعيد القناع والحالة فقط — لا السرّ.

خدمةٌ موحّدة لكل التكاملات (دفع الضيوف · قنوات OTA · الزكاة · شموس · NTMP)
بدل ازدواج الجداول والمصادر.
"""
from __future__ import annotations

import json
import logging

from services import guest_crypto

log = logging.getLogger("dheuof.integration_credentials")


def _pg(db) -> bool:
    return bool(getattr(db, "use_postgres", False))


def _hint(secret: dict) -> str:
    """قناعٌ آمن للعرض من أبرز حقلٍ سرّي — لا يكشف القيمة."""
    for k in ("api_key", "secret_key", "password", "token", "key"):
        v = str((secret or {}).get(k) or "")
        if v:
            return (v[:3] + "••••" + v[-3:]) if len(v) > 6 else "••••"
    return "••••"


def save(db, client_id: str, service: str, secret: dict) -> dict:
    """يحفظ اعتماد مشترك مشفّراً. يعيد الحالة المقنّعة (لا السرّ).

    بلا تشفيرٍ مُفعَّل أو PostgreSQL: لا يُحفَظ سرٌّ حقيقي (لا نصّ صريح) —
    يعيد persisted=False بوضوح.
    """
    if not isinstance(secret, dict) or not any(str(v).strip() for v in secret.values()):
        return {"persisted": False, "error": "empty_secret"}
    hint = _hint(secret)
    if not _pg(db):
        return {"service": service, "connected": False, "persisted": False,
                "key_hint": hint}
    if not guest_crypto.is_enabled():
        # لا نخزّن اعتماداً حقيقياً بلا تشفير — بوّابة أمان لا تُتجاوز.
        log.error("integration secret refused: encryption not configured")
        return {"persisted": False, "error": "encryption_not_configured"}
    enc = guest_crypto.encrypt(json.dumps(secret, ensure_ascii=False))
    db.execute(
        """INSERT INTO integration_credentials
             (client_id, service, secret_enc, key_hint, enabled, updated_at)
           VALUES (%s, %s, %s, %s, TRUE, NOW())
           ON CONFLICT (client_id, service)
           DO UPDATE SET secret_enc=EXCLUDED.secret_enc, key_hint=EXCLUDED.key_hint,
                         enabled=TRUE, updated_at=NOW()""",
        (client_id, service, enc, hint))
    return {"service": service, "connected": True, "persisted": True, "key_hint": hint}


def get(db, client_id: str, service: str) -> dict | None:
    """يفكّ اعتماد المشترك للاستخدام في المحوّل (لا لـHTTP). None إن غاب/مُعطَّل."""
    if not _pg(db):
        return None
    row = db.execute(
        """SELECT secret_enc FROM integration_credentials
           WHERE client_id=%s AND service=%s AND enabled=TRUE""",
        (client_id, service), fetch="one")
    if not row or not row.get("secret_enc"):
        return None
    try:
        return json.loads(guest_crypto.decrypt(row["secret_enc"]) or "{}")
    except Exception as e:
        log.error("failed to decrypt integration secret for %s/%s: %s",
                  client_id, service, e)
        return None


def status(db, client_id: str, service: str | None = None) -> list[dict]:
    """حالة اعتمادات المشترك — مقنّعة، بلا سرّ. خدمةٌ واحدة أو الكل."""
    if not _pg(db):
        return []
    if service:
        rows = db.execute(
            """SELECT service, key_hint, enabled, updated_at
               FROM integration_credentials WHERE client_id=%s AND service=%s""",
            (client_id, service), fetch="all") or []
    else:
        rows = db.execute(
            """SELECT service, key_hint, enabled, updated_at
               FROM integration_credentials WHERE client_id=%s ORDER BY service""",
            (client_id,), fetch="all") or []
    return [{"service": r["service"], "key_hint": r["key_hint"],
             "connected": bool(r["enabled"]),
             "updated_at": (r["updated_at"].isoformat()
                            if r.get("updated_at") else None)}
            for r in (dict(x) for x in rows)]


def delete(db, client_id: str, service: str) -> bool:
    """يفصل اعتماد خدمةٍ لهذا المشترك (تحت تصرّفه)."""
    if not _pg(db):
        return False
    db.execute(
        "DELETE FROM integration_credentials WHERE client_id=%s AND service=%s",
        (client_id, service))
    return True
