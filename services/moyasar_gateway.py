#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/moyasar_gateway.py — نداءات بوابة ميسر (إنشاء دفعة · تحقّق).

- **وضع الاختبار** — مفتاحٌ يبدأ بـ`sk_test_` يعني ساعات اختبار ميسر؛
  `is_test_mode()` يميّزه كي لا نطلق في الحيّ بمفتاح اختبار أو العكس.
- **الإيديمبوتنسي** — كل إنشاء دفعةٍ يحمل مفتاحاً فريداً (`Idempotency-Key`)
  فإعادة المحاولة على انقطاعٍ لا تُنشئ دفعتين.
- **الحقن** — دالة الـHTTP تُحقَن (`http=`) فتُختبَر بلا شبكة. المبالغ
  تُرسَل بالوحدة الصغرى (هللات) عبر services.billing_money.

لا يلمس قاعدة البيانات: نداءٌ صرفٌ للبوابة. المسار هو من يربط النتيجة
بالمنشأة ويسجّلها.
"""
from __future__ import annotations

import os
import secrets

API_BASE = "https://api.moyasar.com/v1"


def api_key() -> str:
    """مفتاح ميسر السرّي من البيئة (لا من الكود)."""
    return (os.environ.get("MOYASAR_SECRET_KEY") or "").strip()


def is_test_mode(key: str | None = None) -> bool:
    """مفتاح اختبار ميسر يبدأ بـsk_test_."""
    k = api_key() if key is None else key
    return k.startswith("sk_test_")


def is_live_key(key: str | None = None) -> bool:
    k = api_key() if key is None else key
    return k.startswith("sk_live_")


def new_idempotency_key() -> str:
    return "idem_" + secrets.token_hex(16)


def _default_http(method, url, headers=None, json=None, auth=None, timeout=20):
    import requests
    return requests.request(method, url, headers=headers, json=json,
                            auth=auth, timeout=timeout)


def create_payment(amount_minor: int, currency: str, description: str,
                   client_id: str, source: dict, *,
                   reference: str | None = None,
                   idempotency_key: str | None = None,
                   callback_url: str | None = None,
                   key: str | None = None, http=None) -> dict:
    """يُنشئ دفعةً في ميسر ويعيد نتيجةً منظَّمة.

    metadata تحمل client_id (فيربط الويب هوك الدفعة بالمنشأة) وreference.
    مفتاح الإيديمبوتنسي يُولَّد إن لم يُمرَّر. مفتاحٌ فارغ → خطأٌ صريح، لا
    نداء صامت.
    """
    key = api_key() if key is None else key
    if not key:
        return {"ok": False, "error": "no_api_key"}
    if not isinstance(amount_minor, int) or amount_minor <= 0:
        return {"ok": False, "error": "invalid_amount"}
    http = http or _default_http
    idem = idempotency_key or new_idempotency_key()
    body = {
        "amount": amount_minor,
        "currency": str(currency or "SAR").upper(),
        "description": description or "",
        "source": source,
        "metadata": {"client_id": client_id, "reference": reference or ""},
    }
    if callback_url:
        body["callback_url"] = callback_url
    try:
        resp = http("POST", f"{API_BASE}/payments",
                    headers={"Idempotency-Key": idem},
                    json=body, auth=(key, ""))
        data = resp.json()
    except Exception as e:                        # لا نُوهم بنجاحٍ لم يقع
        return {"ok": False, "error": "gateway_unreachable", "detail": str(e)}
    status = getattr(resp, "status_code", 200)
    if status >= 400:
        return {"ok": False, "error": "gateway_rejected", "status": status,
                "detail": data, "idempotency_key": idem}
    return {"ok": True, "payment_id": data.get("id"), "status": data.get("status"),
            "test_mode": is_test_mode(key), "idempotency_key": idem, "raw": data}


def fetch_payment(payment_id: str, *, key: str | None = None, http=None) -> dict:
    """يتحقّق من دفعةٍ لدى ميسر (مصدر الحقيقة، لا حمولة العميل)."""
    key = api_key() if key is None else key
    if not key:
        return {"ok": False, "error": "no_api_key"}
    if not payment_id:
        return {"ok": False, "error": "no_payment_id"}
    http = http or _default_http
    try:
        resp = http("GET", f"{API_BASE}/payments/{payment_id}", auth=(key, ""))
        data = resp.json()
    except Exception as e:
        return {"ok": False, "error": "gateway_unreachable", "detail": str(e)}
    if getattr(resp, "status_code", 200) >= 400:
        return {"ok": False, "error": "not_found", "detail": data}
    return {"ok": True, "payment_id": data.get("id"), "status": data.get("status"),
            "raw": data}


def refund_payment(payment_id: str, amount_minor: int | None = None, *,
                   idempotency_key: str | None = None,
                   key: str | None = None, http=None) -> dict:
    """يطلب استرداداً (كاملاً أو جزئياً) — الاسترداد الفعلي يؤكّده الويب هوك."""
    key = api_key() if key is None else key
    if not key:
        return {"ok": False, "error": "no_api_key"}
    if not payment_id:
        return {"ok": False, "error": "no_payment_id"}
    http = http or _default_http
    idem = idempotency_key or new_idempotency_key()
    body = {}
    if amount_minor is not None:
        body["amount"] = amount_minor
    try:
        resp = http("POST", f"{API_BASE}/payments/{payment_id}/refund",
                    headers={"Idempotency-Key": idem}, json=body, auth=(key, ""))
        data = resp.json()
    except Exception as e:
        return {"ok": False, "error": "gateway_unreachable", "detail": str(e)}
    if getattr(resp, "status_code", 200) >= 400:
        return {"ok": False, "error": "refund_rejected", "detail": data}
    return {"ok": True, "payment_id": payment_id, "status": data.get("status"),
            "raw": data}
