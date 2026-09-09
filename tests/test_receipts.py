#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_receipts.py — إيصالات البريد (بند: إرسال إيصالات البريد).

تحقّقٌ بالكسر: الإيصال يحمل المبلغ واسم المنشأة، وجسم HTML يُهرّب اسم
منشأةٍ خبيث (<script>)، والعربية تختلف عن الإنجليزية، وسطر الضريبة يظهر
عند وجوده فقط، و`queue_receipt` لا تُوهم بالحفظ في التطوير.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import receipts  # noqa: E402


def _payment(**kw):
    base = {"amount": 230.0, "currency": "SAR", "id": "pay_123",
            "reference": "bk-9", "date": "2026-09-09"}
    base.update(kw)
    return base


class TestBuildReceipt:
    def test_has_amount_and_facility(self):
        msg = receipts.build_receipt(_payment(), {"name": "فندق النور"}, lang="ar")
        assert "230.00 SAR" in msg["body_text"]
        assert "فندق النور" in msg["body_text"]
        assert "فندق النور" in msg["subject"]
        assert "230.00 SAR" in msg["body_html"]

    def test_html_escapes_malicious_facility(self):
        evil = "<script>alert('x')</script>"
        msg = receipts.build_receipt(_payment(), {"name": evil}, lang="en")
        # لا يوجد وسمٌ خام في جسم HTML
        assert "<script>" not in msg["body_html"]
        assert "&lt;script&gt;" in msg["body_html"]

    def test_ar_and_en_differ(self):
        ar = receipts.build_receipt(_payment(), {"name": "X"}, lang="ar")
        en = receipts.build_receipt(_payment(), {"name": "X"}, lang="en")
        assert ar["subject"] != en["subject"]
        assert ar["body_text"] != en["body_text"]
        assert 'dir="rtl"' in ar["body_html"]
        assert 'dir="ltr"' in en["body_html"]

    def test_vat_line_only_when_present(self):
        with_vat = receipts.build_receipt(
            _payment(vat=30.0), {"name": "X"}, lang="ar")
        assert "30.00 SAR" in with_vat["body_text"]
        no_vat = receipts.build_receipt(_payment(), {"name": "X"}, lang="ar")
        assert receipts._L["ar"]["vat"] not in no_vat["body_text"]

    def test_includes_payment_id_and_reference(self):
        msg = receipts.build_receipt(_payment(), {"name": "X"}, lang="en")
        assert "pay_123" in msg["body_text"]
        assert "bk-9" in msg["body_text"]

    def test_unknown_lang_falls_back_to_ar(self):
        msg = receipts.build_receipt(_payment(), {"name": "X"}, lang="fr")
        assert 'dir="rtl"' in msg["body_html"]

    def test_missing_amount_is_zero_not_crash(self):
        msg = receipts.build_receipt({"id": "p"}, {"name": "X"}, lang="ar")
        assert "0.00 SAR" in msg["body_text"]


class _DevDB:
    use_postgres = False


class _PgDB:
    use_postgres = True

    def __init__(self):
        self.calls = []

    def execute(self, q, p=None, fetch=None):
        self.calls.append((q, p, fetch))
        if "INSERT INTO receipt_intents" in q:
            return {"id": 1}
        return None


class TestQueueReceipt:
    def test_dev_mode_does_not_pretend_to_persist(self):
        res = receipts.queue_receipt(_DevDB(), _payment(), {"name": "X"})
        assert res == {"sent": False, "persisted": False,
                       "subject": res["subject"], "to": None}
        assert res["persisted"] is False

    def test_pg_mode_records_intent(self):
        db = _PgDB()
        res = receipts.queue_receipt(
            db, _payment(), {"id": "h1", "name": "X", "email": "g@e.com"})
        assert res["persisted"] is True
        assert res["sent"] is False
        assert res["to"] == "g@e.com"
        assert any("INSERT INTO receipt_intents" in c[0] for c in db.calls)
