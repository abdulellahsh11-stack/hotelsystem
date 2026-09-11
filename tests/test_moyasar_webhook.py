#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_moyasar_webhook.py — نواة أمان ويب هوك ميسر (PR1).

يفحص بالكسر: التوقيع (صحيح · خاطئ · بلا سرّ · صيغة sha256=)، تطبيع
الحمولة (هللات→ريال · عملات بلا كسور · المنشأة من metadata)، التصنيف
(مدفوع/فاشل/مسترد)، منع التكرار (dedup)، وتسجيل كل حدث.
"""
import hashlib
import hmac
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import moyasar  # noqa: E402

SECRET = "whsec_test_123"


def _sign(body: bytes, secret=SECRET) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


class _FakeDB:
    """قاعدةٌ صوريّة: تحاكي UNIQUE(dedup_key) و ON CONFLICT DO NOTHING."""
    use_postgres = True

    def __init__(self):
        self.seen: set[str] = set()
        self.rows: list[tuple] = []

    def execute(self, q, p=None, fetch=None):
        if q.startswith("SELECT 1 FROM payment_events"):
            return {"ok": 1} if p[0] in self.seen else None
        if "INSERT INTO payment_events" in q and "webhook_failure" not in q:
            dedup = p[1]
            if dedup is not None and dedup in self.seen:
                return None            # ON CONFLICT DO NOTHING
            if dedup is not None:
                self.seen.add(dedup)
            self.rows.append(p)
            return {"id": len(self.rows)}
        if "webhook_failure" in q:
            self.rows.append(p)
            return None
        return None


class TestSignature:
    def test_valid(self):
        body = b'{"id":"p1"}'
        assert moyasar.verify_signature(body, _sign(body), SECRET) is True

    def test_tampered_body_fails(self):
        body = b'{"id":"p1"}'
        sig = _sign(body)
        assert moyasar.verify_signature(b'{"id":"p2"}', sig, SECRET) is False

    def test_wrong_secret_fails(self):
        body = b'{"id":"p1"}'
        assert moyasar.verify_signature(body, _sign(body, "other"), SECRET) is False

    def test_empty_secret_always_false(self):
        body = b'{"id":"p1"}'
        assert moyasar.verify_signature(body, _sign(body), "") is False

    def test_missing_signature_false(self):
        assert moyasar.verify_signature(b'{}', "", SECRET) is False

    def test_sha256_prefix_accepted(self):
        body = b'{"id":"p1"}'
        assert moyasar.verify_signature(body, "sha256=" + _sign(body), SECRET) is True


class TestParse:
    def test_halalas_to_major(self):
        ev = moyasar.parse_event({"type": "payment_paid",
                                  "data": {"id": "p1", "status": "paid",
                                           "amount": 15000, "currency": "SAR",
                                           "metadata": {"client_id": "h1"}}})
        assert ev["amount"] == 150.0 and ev["currency"] == "SAR"
        assert ev["action"] == "paid" and ev["client_id"] == "h1"
        assert ev["dedup_key"] == "p1:payment_paid"    # نوع الحدث الخام لا الفعل

    def test_zero_decimal_currency(self):
        ev = moyasar.parse_event({"data": {"id": "p2", "status": "paid",
                                           "amount": 500, "currency": "JPY"}})
        assert ev["amount"] == 500.0        # JPY بلا كسور

    def test_three_decimal_currency(self):
        ev = moyasar.parse_event({"data": {"id": "p3", "status": "paid",
                                           "amount": 15000, "currency": "KWD"}})
        assert ev["amount"] == 15.0         # KWD ثلاث خانات

    def test_client_id_only_from_metadata(self):
        # معرّف المنشأة لا يُؤخذ من جذر الحمولة بل من metadata الموقَّعة
        ev = moyasar.parse_event({"client_id": "attacker",
                                  "data": {"id": "p4", "status": "paid",
                                           "amount": 100, "metadata": {}}})
        assert ev["client_id"] is None

    def test_classify(self):
        assert moyasar.classify("paid") == "paid"
        assert moyasar.classify("failed") == "failed"
        assert moyasar.classify("expired") == "failed"
        assert moyasar.classify("refunded") == "refunded"
        assert moyasar.classify("initiated") == "pending"


class TestProcess:
    def _payload(self, pid="p1", status="paid", amount=15000):
        return {"type": f"payment_{status}",
                "data": {"id": pid, "status": status, "amount": amount,
                         "currency": "SAR", "metadata": {"client_id": "h1"}}}

    def test_invalid_signature_rejected_and_alerted(self):
        db = _FakeDB()
        body = json.dumps(self._payload()).encode()
        res = moyasar.process_webhook(db, body, "deadbeef", self._payload())
        assert res["ok"] is False and res["reason"] == "invalid_signature"
        # نُبّه: صفٌّ webhook_failure سُجّل
        assert any("webhook_failure" in str(r) for r in db.rows)

    def test_first_event_processed(self, monkeypatch):
        monkeypatch.setenv("MOYASAR_WEBHOOK_SECRET", SECRET)
        db = _FakeDB()
        body = json.dumps(self._payload()).encode()
        res = moyasar.process_webhook(db, body, _sign(body), self._payload())
        assert res["ok"] is True and res["duplicate"] is False
        assert res["action"] == "paid" and len(db.seen) == 1

    def test_duplicate_event_not_reprocessed(self, monkeypatch):
        monkeypatch.setenv("MOYASAR_WEBHOOK_SECRET", SECRET)
        db = _FakeDB()
        body = json.dumps(self._payload()).encode()
        moyasar.process_webhook(db, body, _sign(body), self._payload())
        res2 = moyasar.process_webhook(db, body, _sign(body), self._payload())
        assert res2["ok"] is True and res2["duplicate"] is True
        assert len(db.rows) == 1        # لم تُدرَج دفعة/حدثٌ ثانٍ

    def test_paid_then_refund_both_process(self, monkeypatch):
        monkeypatch.setenv("MOYASAR_WEBHOOK_SECRET", SECRET)
        db = _FakeDB()
        for status in ("paid", "refunded"):
            pl = self._payload(status=status)
            body = json.dumps(pl).encode()
            res = moyasar.process_webhook(db, body, _sign(body), pl)
            assert res["duplicate"] is False
        assert len(db.seen) == 2        # payment_paid و payment_refunded


class TestFixes:
    """إصلاحات مراجعة الكود: الخطة من metadata · نوع الحدث للـdedup ·
    الحمولة الخام للتدقيق · تحرير الحجز عند فشل التطبيق."""

    def test_plan_and_months_from_metadata(self):
        ev = moyasar.parse_event({"type": "payment_paid",
                                  "data": {"id": "p1", "status": "paid", "amount": 100,
                                           "metadata": {"client_id": "h1",
                                                        "plan": "business", "months": "3"}}})
        assert ev["plan"] == "business" and ev["months"] == 3

    def test_plan_parsed_from_reference(self):
        ev = moyasar.parse_event({"type": "payment_paid",
                                  "data": {"id": "p2", "status": "paid", "amount": 100,
                                           "metadata": {"client_id": "h1",
                                                        "reference": "sub:enterprise"}}})
        assert ev["plan"] == "enterprise"

    def test_authorized_and_captured_not_collapsed(self):
        # نوعان مختلفان لنفس الدفعة → مفتاحان مختلفان (لا يبتلع القبضُ الإذنَ)
        auth = moyasar.parse_event({"type": "payment_authorized",
                                    "data": {"id": "p3", "status": "authorized", "amount": 100}})
        cap = moyasar.parse_event({"type": "payment_captured",
                                   "data": {"id": "p3", "status": "captured", "amount": 100}})
        assert auth["dedup_key"] != cap["dedup_key"]

    def test_raw_column_stores_original_payload(self):
        pl = {"type": "payment_paid", "id": "root",
              "data": {"id": "p4", "status": "paid", "amount": 100,
                       "metadata": {"client_id": "h1"}}}
        ev = moyasar.parse_event(pl)
        assert ev["payload"] is pl        # الحمولة الأصلية محفوظة للتدقيق
