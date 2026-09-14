#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_maintenance_report.py — موقع تذكرة الصيانة واستهلاك موادها.

يتبع مثال المستخدم: مستودع صيانة (إضاءة بيضاء ٢٠ · صفراء ٣٠ · مفاتيح ٣٠ ·
سلك ٦٠م). تذكرةٌ لغرفة/ممر/خارج/دور، وعند الإنجاز يُخصَم المستخدَم:
إضاءة صفراء ١ · سلك ١م · مفتاح ١.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import maintenance_report as mr  # noqa: E402
from services import maintenance_stock as ms  # noqa: E402


class TestLocation:
    def test_known_types(self):
        assert mr.normalize_location("room") == "room"
        assert mr.normalize_location("CORRIDOR") == "corridor"
        assert mr.normalize_location("outside") == "outside"
        assert mr.normalize_location("floor") == "floor"

    def test_unknown_is_none(self):
        assert mr.normalize_location("balcony") is None
        assert mr.normalize_location("") is None

    def test_label(self):
        assert mr.location_label("room", "101") == "غرفة — 101"
        assert mr.location_label("corridor", "الشرقي") == "ممر — الشرقي"
        assert mr.location_label("floor", "") == "دور"

    def test_report_trimmed(self):
        assert mr.clean_report("  تم الاستبدال  ") == "تم الاستبدال"
        assert len(mr.clean_report("x" * 5000)) == 2000


class _FakeDB:
    """مستودع صيانة صوريّ (بمعرّفات) لاختبار الخصم بلا هبوطٍ تحت الصفر."""
    use_postgres = True

    def __init__(self):
        self.items = {
            1: {"id": 1, "name": "إضاءة 15 واط بيضاء", "quantity": 20},
            2: {"id": 2, "name": "إضاءة 12 واط صفراء", "quantity": 30},
            3: {"id": 3, "name": "مفتاح نور", "quantity": 30},
            4: {"id": 4, "name": "سلك إضاءة (متر)", "quantity": 60},
        }
        self.movements = []

    def execute(self, q, p=None, fetch=None):
        nq = " ".join(q.split())
        if nq.startswith("UPDATE warehouse_items SET quantity = GREATEST"):
            qty, iid, cid = p
            it = self.items.get(iid)
            if not it:
                return None
            it["quantity"] = max(it["quantity"] - qty, 0)
            return {"id": iid, "name": it["name"], "quantity": it["quantity"]}
        if "INSERT INTO warehouse_movements" in nq:
            self.movements.append(p)
            return None
        return None


class TestConsume:
    def test_users_example(self):
        db = _FakeDB()
        # صفراء ١ · سلك ١م · مفتاح ١
        used = ms.consume(db, "h1", [{"item_id": 2, "qty": 1},
                                     {"item_id": 4, "qty": 1},
                                     {"item_id": 3, "qty": 1}], order_ref="MO-1")
        remaining = {u["name"]: u["remaining"] for u in used}
        assert remaining["إضاءة 12 واط صفراء"] == 29
        assert remaining["سلك إضاءة (متر)"] == 59
        assert remaining["مفتاح نور"] == 29
        assert db.items[1]["quantity"] == 20        # البيضاء لم تُمَسّ
        assert len(db.movements) == 3               # حركةٌ لكل صنف

    def test_no_negative(self):
        db = _FakeDB()
        used = ms.consume(db, "h1", [{"item_id": 4, "qty": 100}], order_ref="MO-2")
        assert used[0]["remaining"] == 0            # ٦٠م، طُلب ١٠٠ → صفر لا سالب

    def test_merges_duplicate_lines(self):
        # سطران لنفس الصنف يُجمعان فلا يُخصَم مرّتين بشكلٍ منفصل
        lines = ms.sanitize_lines([{"item_id": 2, "qty": 1}, {"item_id": 2, "qty": 2}])
        assert lines == [{"item_id": 2, "qty": 3}]
