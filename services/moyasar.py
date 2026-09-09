#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/moyasar.py — نواة تكامل بوابة الدفع (ميسر): أمان الويب هوك.

قبل قلب ميسر إلى الوضع الحيّ، هذا الملف يحرس ما يصل من البوابة:

- **التحقق من التوقيع** — HMAC-SHA256 على الجسم الخام بسرٍّ من البيئة،
  مقارنةً بزمنٍ ثابت. حمولةٌ بلا توقيعٍ صحيح لا تُعالَج أبداً.
- **الإيديمبوتنسي / منع الرسوم المكرّرة** — لكل حدثٍ مفتاحٌ فريد
  (`dedup_key`)؛ إدراجه بـ`ON CONFLICT DO NOTHING`، فإعادة إرسال ميسر
  للحدث نفسه لا تُسجّل دفعةً ثانية.
- **تسجيل كل حدث** — ينزل في `payment_events` بحمولته الخام وحالته.
- **المدفوعات الفاشلة والاستردادات** — تُصنَّف وتُسجَّل بحالتها.
- **التنبيه عند فشل الويب هوك** — توقيعٌ خاطئ أو استثناءٌ أثناء المعالجة
  يُسجَّل بحالة `alert` ويُرفع في سجلّ الخادم كي يراه التشغيل.

منطق التحقق والتصنيف **خالصٌ** (بلا قاعدة بيانات) كي يُختبَر بالكسر؛
لمس القاعدة معزولٌ في دوالٍّ تحرس `use_postgres` كما في services/payments.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os

log = logging.getLogger("dheuof.moyasar")

# حالات ميسر → فعلٌ داخلي موحّد.
_PAID = {"paid", "captured", "authorized"}
_FAILED = {"failed", "declined", "expired", "voided"}
_REFUNDED = {"refunded", "partially_refunded"}


def webhook_secret() -> str:
    """سرّ توقيع الويب هوك من البيئة — فارغٌ يعني رفض كل حدث."""
    return (os.environ.get("MOYASAR_WEBHOOK_SECRET") or "").strip()


def verify_signature(raw_body: bytes, provided: str, secret: str | None = None) -> bool:
    """HMAC-SHA256 على الجسم الخام، مقارنةً بزمنٍ ثابت.

    - سرٌّ فارغ → False دائماً (لا نقبل بلا سرٍّ مضبوط).
    - توقيعٌ غائب/فارغ → False.
    - يقبل التوقيع بصيغة hex عارية أو مسبوقة بـ`sha256=` (كعادة عدّة بوّابات).
    """
    secret = webhook_secret() if secret is None else (secret or "").strip()
    if not secret or not provided:
        return False
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    provided = provided.strip()
    if provided.lower().startswith("sha256="):
        provided = provided[7:]
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided.lower())


def _to_major(amount, currency) -> float:
    """ميسر يرسل المبلغ بأصغر وحدة (هللات). نردّه لوحدةٍ كبرى.

    العملات بلا كسور (JOD/KWD/BHD ثلاث خانات؛ JPY بلا خانات) تُعالَج
    بجدول الأسّ؛ غير المعروف يُعامَل معاملة الريال (خانتان).
    """
    try:
        minor = int(amount)
    except (TypeError, ValueError):
        return 0.0
    exp = _CURRENCY_EXP.get(str(currency or "SAR").upper(), 2)
    return round(minor / (10 ** exp), exp)


# أسّ الوحدة الصغرى لكل عملة (كم خانة كسرية).
_CURRENCY_EXP = {
    "SAR": 2, "USD": 2, "EUR": 2, "AED": 2, "EGP": 2, "QAR": 2,
    "JPY": 0, "KWD": 3, "BHD": 3, "JOD": 3, "OMR": 3,
}


def classify(status) -> str:
    """حالة ميسر → فعلٌ داخلي: paid | failed | refunded | pending."""
    s = str(status or "").strip().lower()
    if s in _PAID:
        return "paid"
    if s in _FAILED:
        return "failed"
    if s in _REFUNDED:
        return "refunded"
    return "pending"


def parse_event(payload: dict) -> dict:
    """يُطبّع حمولة ميسر إلى حقولٍ نتعامل بها.

    ميسر يغلّف الدفعة إمّا مباشرةً أو تحت `data`. المنشأة تأتي من
    `metadata.client_id` الذي نضعه نحن عند إنشاء الدفعة — لا من مصدرٍ
    يتحكّم به الدافع.
    """
    p = payload if isinstance(payload, dict) else {}
    data = p.get("data") if isinstance(p.get("data"), dict) else p
    status = data.get("status") or p.get("status")
    meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
    payment_id = str(data.get("id") or p.get("id") or "")
    event_type = str(p.get("type") or data.get("type") or "").strip().lower()
    currency = data.get("currency") or "SAR"
    action = classify(status)
    # مفتاح منع التكرار: معرّف الدفعة + الفعل (فحدثان مختلفان لنفس الدفعة
    # — دفعٌ ثم استرداد — يُعالَجان، وإعادةُ الحدث نفسه لا تتكرّر).
    dedup = f"{payment_id}:{action}" if payment_id else ""
    return {
        "payment_id": payment_id,
        "event_type": event_type or action,
        "status": str(status or "").strip().lower(),
        "action": action,
        "amount": _to_major(data.get("amount"), currency),
        "currency": str(currency).upper(),
        "client_id": str(meta.get("client_id") or "").strip() or None,
        "reference": str(meta.get("reference") or data.get("description") or "").strip() or None,
        "dedup_key": dedup,
    }


# ── لمس القاعدة (معزولٌ، يحرس use_postgres) ─────────────────────────

def _pg(db) -> bool:
    return bool(getattr(db, "use_postgres", False))


def already_processed(db, dedup_key: str) -> bool:
    """هل عولج هذا الحدث من قبل؟ (فارغٌ لا يُعدّ معالَجاً)."""
    if not dedup_key or not _pg(db):
        return False
    row = db.execute(
        "SELECT 1 FROM payment_events WHERE dedup_key=%s", (dedup_key,), fetch="one")
    return bool(row)


def log_event(db, ev: dict, status: str) -> dict:
    """يُدرج الحدث في payment_events مرّةً واحدة (ON CONFLICT DO NOTHING).

    يعيد {"logged": bool, "duplicate": bool}. في التطوير (بلا PostgreSQL)
    لا يُخزَّن ولا يُوهم بالحفظ.
    """
    if not _pg(db):
        return {"logged": False, "duplicate": False, "persisted": False}
    dedup = ev.get("dedup_key") or None
    row = db.execute(
        """INSERT INTO payment_events
             (client_id, dedup_key, event_type, payment_id, amount, currency, status, raw)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (dedup_key) DO NOTHING
           RETURNING id""",
        (ev.get("client_id"), dedup, ev.get("event_type"), ev.get("payment_id"),
         ev.get("amount"), ev.get("currency"), status,
         json.dumps(ev.get("raw") or ev, ensure_ascii=False)),
        fetch="one")
    logged = bool(row)
    return {"logged": logged, "duplicate": (dedup is not None and not logged),
            "persisted": True}


def alert_webhook_failure(db, reason: str, ev: dict | None = None) -> None:
    """يُسجّل فشل ويب هوك بحالة `alert` ويرفعه في سجلّ الخادم.

    البريد الفعليّ للتنبيه طبقةٌ تالية؛ هنا نضمن أثراً لا يضيع.
    """
    log.error("⚠️ Moyasar webhook failure: %s | %s", reason,
              (ev or {}).get("payment_id") or "no-payment-id")
    if not _pg(db):
        return
    try:
        db.execute(
            """INSERT INTO payment_events
                 (client_id, dedup_key, event_type, payment_id, status, raw)
               VALUES (%s, %s, %s, %s, 'alert', %s)
               ON CONFLICT (dedup_key) DO NOTHING""",
            ((ev or {}).get("client_id"), None, "webhook_failure",
             (ev or {}).get("payment_id"),
             json.dumps({"reason": reason, "event": ev}, ensure_ascii=False)))
    except Exception as e:                       # التنبيه لا يُسقط المعالجة
        log.error("failed to persist webhook alert: %s", e)


def process_webhook(db, raw_body: bytes, signature: str,
                    payload: dict) -> dict:
    """المعالجة الكاملة لحدث ويب هوك — تُرجع نتيجةً منظَّمة.

    الترتيب: تحقّق التوقيع → تطبيع → منع التكرار → تسجيل → تصنيف الفعل.
    التسجيل الفعلي للدفعة/الاسترداد في payments، ومزامنة الاشتراك، يبنيان
    فوق هذه النتيجة (بندٌ تالٍ). أي رفضٍ أو خطأٍ يُنبَّه عليه.
    """
    if not verify_signature(raw_body, signature):
        alert_webhook_failure(db, "invalid_signature")
        return {"ok": False, "reason": "invalid_signature", "action": None}

    ev = parse_event(payload)
    if already_processed(db, ev["dedup_key"]):
        return {"ok": True, "duplicate": True, "action": ev["action"],
                "event": ev}

    res = log_event(db, ev, status="received")
    if res.get("duplicate"):                     # سباقٌ: أدرجه طلبٌ متزامن
        return {"ok": True, "duplicate": True, "action": ev["action"],
                "event": ev}
    return {"ok": True, "duplicate": False, "action": ev["action"], "event": ev}


def apply_business(store, ev: dict) -> dict:
    """يعكس الحدث على الأعمال بعد التحقّق والتسجيل ومنع التكرار.

    - **مدفوع** → يفعّل/يمدّد اشتراك المنشأة (مزامنة الحالة مع القاعدة)
      ويسجّل الدفعة في payments.
    - **مسترد** → يعيد المنشأة إلى «متأخّرة» كي تراجَع (لا نقفل تلقائياً
      دون قرارٍ إداري).
    - **فاشل** → لا تغيير في الوصول؛ الحدث مسجَّلٌ للمتابعة.

    المنشأة من metadata الموقَّعة (ev['client_id'])؛ حدثٌ بلا منشأة لا
    يُطبَّق. يحرس لمس القاعدة use_postgres.
    """
    from services import payments, receipts, subscription

    cid = ev.get("client_id")
    action = ev.get("action")
    if not cid:
        return {"applied": False, "reason": "no_client"}
    db = getattr(store, "db", None) or store
    client = store.get_client(cid) if hasattr(store, "get_client") else None
    if action == "paid":
        months = int((ev.get("raw") or {}).get("months") or 1)
        plan = (ev.get("raw") or {}).get("plan") or (client or {}).get("plan") or "starter"
        updates = subscription.activate(client, plan, months)
        _save_account(store, client, cid, updates)
        payments.record(db, cid, ev.get("amount"), method="online",
                        reference=ev.get("payment_id"))
        receipts.queue_receipt(db, {"amount": ev.get("amount"),
                                    "currency": ev.get("currency"),
                                    "payment_id": ev.get("payment_id"),
                                    "reference": ev.get("reference")},
                               client or {"id": cid})
        return {"applied": True, "action": "activated", "sub_end": updates["sub_end"]}
    if action == "refunded":
        _save_account(store, client, cid, {"status": "past_due"})
        return {"applied": True, "action": "past_due"}
    return {"applied": False, "reason": action}


def _save_account(store, client, cid: str, updates: dict) -> None:
    """يحفظ حقول الحساب دون لمس settings._account مباشرةً."""
    if not hasattr(store, "save_client"):
        return
    c = dict(client or {"id": cid})
    c.setdefault("id", cid)
    c.update(updates)
    store.save_client(c)
