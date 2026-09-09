#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_moyasar_gateway.py — نداءات بوابة ميسر (بلا شبكة، http محقون).

يفحص بالكسر: وضع الاختبار من المفتاح، مفتاح إيديمبوتنسي فريد لكل إنشاء،
رفض المبلغ ≤ صفر والمفتاح الفارغ، شكل نداء الإنشاء (metadata فيها client_id،
Idempotency-Key)، ومعالجة رفض البوابة (≥400) دون إيهامٍ بنجاح.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import moyasar_gateway as gw  # noqa: E402

KEY = "sk_test_abc123"


class _Resp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class _HTTP:
    """يلتقط النداء ويعيد ردّاً مُعدّاً."""
    def __init__(self, status=200, payload=None):
        self.calls = []
        self._status = status
        self._payload = payload or {"id": "pay_1", "status": "initiated"}

    def __call__(self, method, url, headers=None, json=None, auth=None, timeout=20):
        self.calls.append({"method": method, "url": url, "headers": headers,
                           "json": json, "auth": auth})
        return _Resp(self._status, self._payload)


class TestMode:
    def test_test_key_detected(self):
        assert gw.is_test_mode("sk_test_x") is True
        assert gw.is_test_mode("sk_live_x") is False
        assert gw.is_live_key("sk_live_x") is True

    def test_unique_idempotency_keys(self):
        assert gw.new_idempotency_key() != gw.new_idempotency_key()


class TestCreatePayment:
    def test_rejects_empty_key(self):
        assert gw.create_payment(100, "SAR", "d", "h1", {}, key="")["error"] == "no_api_key"

    def test_rejects_non_positive_amount(self):
        assert gw.create_payment(0, "SAR", "d", "h1", {}, key=KEY)["error"] == "invalid_amount"
        assert gw.create_payment(-5, "SAR", "d", "h1", {}, key=KEY)["error"] == "invalid_amount"

    def test_success_shape_and_metadata(self):
        http = _HTTP(200, {"id": "pay_9", "status": "initiated"})
        res = gw.create_payment(15000, "SAR", "اشتراك", "h1", {"type": "creditcard"},
                                reference="sub-1", key=KEY, http=http)
        assert res["ok"] is True and res["payment_id"] == "pay_9"
        assert res["test_mode"] is True
        call = http.calls[0]
        assert call["json"]["metadata"]["client_id"] == "h1"
        assert call["json"]["metadata"]["reference"] == "sub-1"
        assert call["json"]["amount"] == 15000
        assert call["headers"]["Idempotency-Key"] == res["idempotency_key"]
        assert call["auth"] == (KEY, "")

    def test_passes_supplied_idempotency_key(self):
        http = _HTTP()
        gw.create_payment(100, "SAR", "d", "h1", {}, idempotency_key="idem_fixed",
                          key=KEY, http=http)
        assert http.calls[0]["headers"]["Idempotency-Key"] == "idem_fixed"

    def test_gateway_rejection_not_ok(self):
        http = _HTTP(422, {"message": "invalid source"})
        res = gw.create_payment(100, "SAR", "d", "h1", {}, key=KEY, http=http)
        assert res["ok"] is False and res["error"] == "gateway_rejected"
        assert res["status"] == 422

    def test_network_error_no_false_success(self):
        def boom(*a, **k):
            raise ConnectionError("down")
        res = gw.create_payment(100, "SAR", "d", "h1", {}, key=KEY, http=boom)
        assert res["ok"] is False and res["error"] == "gateway_unreachable"


class TestFetchRefund:
    def test_fetch_payment(self):
        http = _HTTP(200, {"id": "pay_2", "status": "paid"})
        res = gw.fetch_payment("pay_2", key=KEY, http=http)
        assert res["ok"] is True and res["status"] == "paid"
        assert http.calls[0]["method"] == "GET"

    def test_fetch_missing_id(self):
        assert gw.fetch_payment("", key=KEY)["error"] == "no_payment_id"

    def test_refund_success(self):
        http = _HTTP(200, {"status": "refunded"})
        res = gw.refund_payment("pay_3", amount_minor=5000, key=KEY, http=http)
        assert res["ok"] is True and res["status"] == "refunded"
        assert http.calls[0]["json"]["amount"] == 5000
        assert "Idempotency-Key" in http.calls[0]["headers"]
