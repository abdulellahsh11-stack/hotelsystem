#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_subscription_sync.py — مزامنة الاشتراك والحمايات الخادمية (PR2).

يفحص بالكسر: بدء التجربة، التفعيل/التمديد (لا تضيع أيام)، الترقية/الهبوط،
الإلغاء الذي يُبقي الوصول، الحماية الخادمية للوحدات، وعكس حدث ميسر المدفوع
على اشتراك المنشأة (البند ٧: مزامنة الحالة مع القاعدة).
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import moyasar, subscription as sub  # noqa: E402

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


class TestStateMachine:
    def test_trial_is_30_days(self):
        t = sub.start_trial(NOW)
        assert t["status"] == "trial" and t["sub_end"] == "2026-01-31"

    def test_activate_from_now(self):
        a = sub.activate({}, "starter", months=1, now=NOW)
        assert a["status"] == "active" and a["plan"] == "starter"
        assert a["sub_end"] == "2026-02-01"

    def test_early_renew_extends_from_existing_end(self):
        client = {"sub_end": "2026-03-01", "plan": "starter"}
        a = sub.activate(client, "starter", months=1, now=NOW)
        assert a["sub_end"] == "2026-04-01"      # يمدّد من الأبعد لا من الآن

    def test_upgrade_downgrade_direction(self):
        assert sub.change_plan({"plan": "starter"}, "business")["direction"] == "upgrade"
        assert sub.change_plan({"plan": "enterprise"}, "starter")["direction"] == "downgrade"
        assert sub.change_plan({"plan": "business"}, "business")["direction"] == "same"

    def test_cancel_keeps_access_until_end(self):
        client = {"status": "active", "sub_end": "2026-02-01"}
        client.update(sub.cancel(client))
        assert client["status"] == "canceled"
        assert sub.is_accessible(client, now=NOW) is True     # لم تنقضِ المدّة

    def test_suspended_has_no_access(self):
        assert sub.is_accessible({"status": "suspended",
                                  "sub_end": "2027-01-01"}, now=NOW) is False


class TestServerGate:
    def test_plan_below_module_blocked(self):
        client = {"plan": "starter", "status": "active", "sub_end": "2027-01-01"}
        assert sub.can_use(client, "channels", now=NOW) is False   # يحتاج business
        assert sub.can_use(client, "guests", now=NOW) is True      # غير محكوم

    def test_high_plan_allowed(self):
        client = {"plan": "enterprise", "status": "active", "sub_end": "2027-01-01"}
        assert sub.can_use(client, "api", now=NOW) is True

    def test_locked_subscription_blocks_even_high_plan(self):
        client = {"plan": "enterprise", "status": "active", "sub_end": "2025-01-01"}
        assert sub.can_use(client, "api", now=NOW) is False        # مقفل


class _FakeStore:
    use_postgres = False

    def __init__(self, client=None):
        self.saved = None
        self._client = client or {"id": "h1", "plan": "business"}
        self.db = self

    def get_client(self, cid):
        return dict(self._client) if self._client.get("id") == cid else None

    def save_client(self, client):
        self.saved = client
        return client


class TestApplyBusiness:
    def test_paid_activates_subscription(self):
        store = _FakeStore()
        ev = {"client_id": "h1", "action": "paid", "amount": 300.0,
              "payment_id": "p1", "raw": {"plan": "business", "months": 1}}
        res = moyasar.apply_business(store, ev)
        assert res["applied"] is True and res["action"] == "activated"
        assert store.saved["status"] == "active" and store.saved["plan"] == "business"

    def test_no_client_id_not_applied(self):
        store = _FakeStore()
        res = moyasar.apply_business(store, {"client_id": None, "action": "paid"})
        assert res["applied"] is False and store.saved is None

    def test_refund_marks_past_due(self):
        store = _FakeStore()
        res = moyasar.apply_business(store, {"client_id": "h1", "action": "refunded"})
        assert res["applied"] is True and store.saved["status"] == "past_due"
