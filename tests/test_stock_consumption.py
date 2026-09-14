#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_stock_consumption.py — الاستهلاك التلقائي لكل نزيل.

يتبع مثال المستخدم بالضبط: فوط ٣٠٠ (قابلة لإعادة الاستخدام) · شامبو ٥٠٠ ·
ماء ٤٠٠ (مستهلَكان). نزيلٌ واحد → فوط نظيفة ٢٩٩ ومتّسخة ١، شامبو ٤٩٩، ماء ٣٩٩.
نزيلٌ ومرافقٌ (شخصان) → فوط نظيفة ٢٩٨ ومتّسخة ٢، شامبو ٤٩٨، ماء ٣٩٨.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import stock_consumption as stock  # noqa: E402


class _FakeDB:
    """قاعدة صوريّة تحاكي GREATEST/LEAST على النظيف والمتّسخ."""
    use_postgres = True

    def __init__(self):
        # id -> صنف
        self.items = {
            1: {"id": 1, "name": "فوط جسم", "item_kind": "reusable",
                "per_guest": 1, "quantity": 300, "dirty_quantity": 0},
            2: {"id": 2, "name": "شامبو", "item_kind": "consumable",
                "per_guest": 1, "quantity": 500, "dirty_quantity": 0},
            3: {"id": 3, "name": "ماء", "item_kind": "consumable",
                "per_guest": 1, "quantity": 400, "dirty_quantity": 0},
            4: {"id": 4, "name": "لا يُخصم", "item_kind": "consumable",
                "per_guest": 0, "quantity": 50, "dirty_quantity": 0},
        }
        self.movements = []

    def execute(self, q, p=None, fetch=None):
        nq = " ".join(q.split())      # تطبيع المسافات للمطابقة المتينة
        if nq.startswith("SELECT id, name, item_kind, per_guest"):
            return [dict(v) for v in self.items.values() if v["per_guest"] > 0]
        if "INSERT INTO warehouse_movements" in nq:
            self.movements.append(p)
            return None
        # إرجاع الغسيل: المتّسخ→النظيف، مقيّدٌ بـitem_kind='reusable'
        if "item_kind='reusable'" in nq and "dirty_quantity - %s" in nq:
            amt, _, iid, cid = p
            it = self.items.get(iid)
            if not it or it["item_kind"] != "reusable":
                return None
            moved = min(it["dirty_quantity"], amt)
            it["dirty_quantity"] = max(it["dirty_quantity"] - amt, 0)
            it["quantity"] += moved
            return {"quantity": it["quantity"], "dirty_quantity": it["dirty_quantity"]}
        # استهلاك قابل لإعادة الاستخدام: النظيف يَنقص والمتّسخ يزيد
        if "dirty_quantity = dirty_quantity + LEAST" in nq:
            amt, _, iid, cid = p
            it = self.items[iid]
            moved = min(it["quantity"], amt)
            it["quantity"] = max(it["quantity"] - amt, 0)
            it["dirty_quantity"] += moved
            return {"quantity": it["quantity"], "dirty_quantity": it["dirty_quantity"]}
        # استهلاك مستهلَك: نقصٌ نهائي
        if "SET quantity = GREATEST(quantity - %s, 0), updated_at" in nq:
            amt, iid, cid = p
            it = self.items[iid]
            it["quantity"] = max(it["quantity"] - amt, 0)
            return {"quantity": it["quantity"], "dirty_quantity": it["dirty_quantity"]}
        return None


class TestPlan:
    def test_plan_multiplies_by_persons(self):
        items = [{"id": 1, "name": "فوط", "item_kind": "reusable", "per_guest": 1},
                 {"id": 2, "name": "شامبو", "item_kind": "consumable", "per_guest": 1}]
        out = stock.plan(items, persons=2)
        assert {o["name"]: o["amount"] for o in out} == {"فوط": 2, "شامبو": 2}

    def test_zero_rate_ignored(self):
        assert stock.plan([{"id": 4, "per_guest": 0}], persons=3) == []


class TestConsume:
    def test_one_guest(self):
        db = _FakeDB()
        res = stock.consume_for_stay(db, "h1", persons=1)
        assert res["فوط جسم"] == {"kind": "reusable", "amount": 1, "clean": 299, "dirty": 1}
        assert res["شامبو"]["clean"] == 499 and res["ماء"]["clean"] == 399
        assert "لا يُخصم" not in res              # per_guest=0 لا يُخصم

    def test_guest_plus_companion(self):
        db = _FakeDB()
        res = stock.consume_for_stay(db, "h1", persons=2)
        assert res["فوط جسم"]["clean"] == 298 and res["فوط جسم"]["dirty"] == 2
        assert res["شامبو"]["clean"] == 498 and res["ماء"]["clean"] == 398

    def test_reusable_conserves_total(self):
        db = _FakeDB()
        stock.consume_for_stay(db, "h1", persons=5)
        it = db.items[1]
        assert it["quantity"] + it["dirty_quantity"] == 300   # المجموع محفوظ

    def test_no_negative_when_depleted(self):
        db = _FakeDB()
        db.items[2]["quantity"] = 1
        res = stock.consume_for_stay(db, "h1", persons=10)     # يطلب ١٠ من ١
        assert res["شامبو"]["clean"] == 0                      # لا سالب

    def test_laundry_return(self):
        db = _FakeDB()
        stock.consume_for_stay(db, "h1", persons=3)            # فوط: نظيف 297 متّسخ 3
        res = stock.return_from_laundry(db, "h1", 1, 2)        # أرجِع 2
        assert res == {"clean": 299, "dirty": 1}

    def test_laundry_rejects_consumable(self):
        db = _FakeDB()
        assert stock.return_from_laundry(db, "h1", 2, 5) is None   # شامبو ليس قابلاً

    def test_dev_mode_no_persist(self):
        class Dev:
            use_postgres = False
        assert stock.consume_for_stay(Dev(), "h1", 1) == {}
