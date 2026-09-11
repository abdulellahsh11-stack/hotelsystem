#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_billing_flow.py — التدفق كاملاً كعميل (البند ٢٠).

يمشي بالطريق الحقيقي من طرفه: تجربةٌ → دفعةٌ في ميسر → ويب هوك موقَّع →
تفعيلُ الاشتراك + تسجيل الدفعة + إيصال → إعادة إرسال الحدث (لا تكرار) →
استرداد (past_due) → إلغاءٌ يُبقي الوصول. يربط الوحدات كما تعمل في الإنتاج
بمخزنٍ صوريّ، لا بمحاكاةٍ لكلٍّ على حدة.
"""
import hashlib
import hmac
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import (billing_money, moyasar, moyasar_gateway,  # noqa: E402
                      subscription)

SECRET = "whsec_flow"


def _sign(body: bytes) -> str:
    return hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


class _Store:
    """مخزنٌ صوريّ يجمع الحفظ والقاعدة معاً كما في الإنتاج (store.db)."""
    use_postgres = True

    def __init__(self):
        self.clients = {"h1": {"id": "h1", "name": "فندق النور", "plan": "trial",
                               "status": "trial", "email": "gm@nour.sa"}}
        self.payments = []
        self.events = set()
        self.receipts = []
        self.db = self

    # واجهة المخزن
    def get_client(self, cid):
        c = self.clients.get(cid)
        return dict(c) if c else None

    def save_client(self, client):
        self.clients[client["id"]] = dict(client)
        return client

    # واجهة القاعدة (db.execute)
    def execute(self, q, p=None, fetch=None):
        if q.startswith("SELECT 1 FROM payment_events"):
            return {"x": 1} if p[0] in self.events else None
        if "INSERT INTO payment_events" in q and "webhook_failure" not in q:
            dedup = p[1]
            if dedup and dedup in self.events:
                return None
            if dedup:
                self.events.add(dedup)
            return {"id": len(self.events)}
        if "INSERT INTO payments" in q:
            self.payments.append(p)
            return {"id": len(self.payments), "amount": p[1], "method": p[2],
                    "reference": p[3], "device_id": p[4], "created_at": "2026-09-09"}
        if "INSERT INTO receipt_intents" in q:
            self.receipts.append(p)
            return {"id": len(self.receipts)}
        if q.startswith("DELETE FROM payment_events"):     # تحرير الحجز
            self.events.discard(p[0])
            return None
        if q.startswith("UPDATE payment_events SET status"): # received→processed
            return None
        return None


def _paid_webhook(pid="pay_1", amount_minor=45885, status="paid"):
    """حمولة ويب هوك ميسر لدفعةٍ — المبلغ بالهللات، المنشأة في metadata."""
    return {"type": f"payment_{status}",
            "data": {"id": pid, "status": status, "amount": amount_minor,
                     "currency": "SAR",
                     "metadata": {"client_id": "h1", "plan": "business",
                                  "reference": "sub:business"}}}


def _deliver(store, payload):
    body = json.dumps(payload).encode()
    res = moyasar.process_webhook(store.db, body, _sign(body), payload)
    if res.get("ok") and not res.get("duplicate"):
        # نُمرّر plan/months كما يفعل المسار عبر raw
        res["event"]["raw"] = {"plan": payload["data"]["metadata"].get("plan"),
                               "months": 1}
        moyasar.apply_business(store, res["event"])
    return res


class TestFullCustomerJourney:
    def setup_method(self, _):
        os.environ["MOYASAR_WEBHOOK_SECRET"] = SECRET

    def test_checkout_amount_is_price_plus_vat_in_halalas(self):
        # ما ترسله بوابة الفوترة: 399 + 15% = 458.85 ريال → 45885 هللة
        total = billing_money.add_vat(399.0)["total"]
        assert total == 458.85
        assert billing_money.to_minor(total, "SAR") == 45885

    def test_gateway_create_is_idempotent_shape(self):
        calls = []

        def http(method, url, headers=None, json=None, auth=None, timeout=20):
            calls.append(headers["Idempotency-Key"])
            class R:
                status_code = 200
                def json(self_):
                    return {"id": "pay_1", "status": "initiated"}
            return R()
        r = moyasar_gateway.create_payment(45885, "SAR", "d", "h1",
                                           {"type": "creditcard"},
                                           key="sk_test_x", http=http)
        assert r["ok"] and r["test_mode"] is True and calls[0] == r["idempotency_key"]

    def test_paid_webhook_activates_records_and_receipts(self):
        store = _Store()
        res = _deliver(store, _paid_webhook())
        assert res["ok"] and res["action"] == "paid"
        # الاشتراك فُعّل بالخطة المدفوعة
        assert store.clients["h1"]["status"] == "active"
        assert store.clients["h1"]["plan"] == "business"
        # دفعةٌ سُجّلت (بالوحدة الكبرى 458.85)
        assert len(store.payments) == 1 and float(store.payments[0][1]) == 458.85
        # إيصالٌ صُفّ للإرسال
        assert len(store.receipts) == 1

    def test_duplicate_webhook_does_not_double_charge(self):
        store = _Store()
        _deliver(store, _paid_webhook())
        res2 = _deliver(store, _paid_webhook())     # نفس الحدث ثانيةً
        assert res2["duplicate"] is True
        assert len(store.payments) == 1             # لا دفعةٌ ثانية
        assert len(store.receipts) == 1

    def test_refund_then_cancel_flow(self):
        store = _Store()
        _deliver(store, _paid_webhook())
        # استرداد → past_due
        _deliver(store, _paid_webhook(pid="pay_1", status="refunded"))
        assert store.clients["h1"]["status"] == "past_due"
        # المنشأة تُلغي — الوصول يبقى حتى نهاية المدّة المدفوعة
        client = store.get_client("h1")
        client.update(subscription.activate(client, "business", 1))  # مدّة سارية
        client.update(subscription.cancel(client))
        store.save_client(client)
        assert store.clients["h1"]["status"] == "canceled"
        assert subscription.is_accessible(store.get_client("h1")) is True

    def test_apply_failure_releases_reservation_for_retry(self, monkeypatch):
        # لو فشل التطبيق (المال قُبض) يجب أن يُحرَّر الحجز فتُعاد المحاولة —
        # لا أن يُعدّ مكرّراً فيضيع التفعيل.
        monkeypatch.setenv("MOYASAR_WEBHOOK_SECRET", SECRET)
        store = _Store()
        calls = {"n": 0}
        real_activate = subscription.activate

        def flaky_activate(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("db blip")
            return real_activate(*a, **k)
        monkeypatch.setattr(subscription, "activate", flaky_activate)

        pl = _paid_webhook()
        body = json.dumps(pl).encode()
        r1 = moyasar.handle_webhook(store.db, store, body, _sign(body), pl)
        assert r1["ok"] is False and r1.get("retry") is True
        assert store.clients["h1"]["status"] == "trial"     # لم يُفعَّل بعد
        assert len(store.events) == 0                        # الحجز حُرِّر

        # إعادة إرسال ميسر تنجح الآن
        r2 = moyasar.handle_webhook(store.db, store, body, _sign(body), pl)
        assert r2["ok"] is True and r2["duplicate"] is False
        assert store.clients["h1"]["status"] == "active"

    def test_tampered_webhook_rejected_end_to_end(self):
        store = _Store()
        payload = _paid_webhook()
        body = json.dumps(payload).encode()
        res = moyasar.process_webhook(store.db, body, "bad_sig", payload)
        assert res["ok"] is False
        assert store.clients["h1"]["status"] == "trial"   # لم يتغيّر شيء
        assert len(store.payments) == 0
