#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_room_status.py — حالات الغرفة وألوانها من مصدرٍ واحد + انتقالات الصيانة

خمس حالاتٍ لكلٍّ لون، والقديم يُطبَّع لا يُرفض. والخريطة ترسل اللون فتعرضه
كل شاشة موحّداً. وانتقالات الصيانة: فتح العطل يُحمّر الغرفة، وإغلاقه يُزرّقها
(نظافة) لا يُخضّرها رأساً — بعد الصيانة تُنظَّف ثم يُصدّرها طاقم التنظيف.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAINT = ROOT / "routes/maintenance.py"
HK = ROOT / "routes/housekeeping.py"


# ── خدمة الحالات ────────────────────────────────────────────────
def test_five_statuses_each_with_a_colour():
    from services import room_status as rs

    assert set(rs.STATUSES) == {"available", "occupied", "cleaning", "maintenance", "renovation"}
    for meta in rs.STATUSES.values():
        assert meta["label"] and meta["color"] and meta["hex"].startswith("#")
    assert len(rs.legend()) == 5


def test_legacy_names_normalize_to_canonical():
    from services import room_status as rs

    assert rs.normalize("dirty") == "cleaning"
    assert rs.normalize("blocked") == "renovation"
    assert rs.normalize("out-of-order") == "renovation"
    assert rs.normalize("ready") == "available"
    assert rs.normalize("nonsense") == "available"   # غير المعروف لا يُكسر


def test_colours_match_the_spec():
    """أخضر جاهزة · أزرق نظافة · أحمر صيانة · رمادي ترميم."""
    from services import room_status as rs

    assert rs.decorate("available")["color"] == "green"
    assert rs.decorate("cleaning")["color"] == "blue"
    assert rs.decorate("maintenance")["color"] == "red"
    assert rs.decorate("renovation")["color"] == "gray"


# ── انتقالات الصيانة في المسار ──────────────────────────────────
def test_opening_a_maintenance_order_reddens_the_room_but_not_an_occupied_one():
    src = MAINT.read_text(encoding="utf-8")
    # تُضبط «maintenance» معزولةً بالمنشأة، لكن لا تُلمَس غرفةٌ «مشغولة»
    # (نزيلٌ بداخلها) فلا يضيع إشغالُها عند إغلاق العطل.
    assert re.search(
        r"UPDATE rooms SET status='maintenance' \"?\s*\n?\s*\"?\s*"
        r"WHERE id=%s AND client_id=%s AND status <> 'occupied'", src
    ), "فتح العطل يجب أن يُحمّر الغرفة إلا المشغولة"
    assert 'prev_status != "occupied"' in src, "لا حارس للغرفة المشغولة قبل التحويل"


def test_closing_a_maintenance_order_turns_the_room_blue_not_green():
    src = MAINT.read_text(encoding="utf-8")
    # الإغلاق يعيدها «cleaning» (أزرق)، وفقط إن كانت ما زالت «maintenance»
    assert re.search(
        r"UPDATE rooms SET status='cleaning'\s+\"?\s*\n?\s*\"?\s*WHERE id=%s AND client_id=%s AND status='maintenance'",
        src,
    ), "إغلاق العطل لا يُحوّل الغرفة إلى نظافة (أزرق) بشرط أنها ما زالت صيانة"


def test_checkout_sends_the_room_to_cleaning():
    """تسجيل الخروج → «cleaning» (أزرق) حتى يُصدّرها طاقم التنظيف."""
    src = HK.read_text(encoding="utf-8")
    assert "status        = 'cleaning'" in src or "status='cleaning'" in src


# ── سجلّ المساءلة: من نفّذ الإجراء ───────────────────────────────
def test_actor_label_prefers_name_then_username_then_role():
    from db.access import actor_label

    assert actor_label({"full_name": "أحمد", "username": "a", "role": "receptionist"}) == "أحمد"
    assert actor_label({"username": "reception1", "role": "receptionist"}) == "reception1"
    # بلا اسمٍ ولا مستخدم → تسمية الدور بالعربية لا فراغ
    assert actor_label({"role": "receptionist"}) == "موظف استقبال"
    assert actor_label({"role": "gm"}) == "مدير عام"


def test_status_change_records_who_and_the_transition():
    """تغيير لون/حالة الغرفة يُسجَّل باسم من غيّره ومن أيّ حالةٍ إلى أيّ."""
    ROUTE = ROOT / "routes/hotel_ops.py"
    src = ROUTE.read_text(encoding="utf-8")
    assert "INSERT INTO room_actions" in src
    assert "'status_change'" in src
    assert "actor_label(session)" in src


def test_guest_registration_stamps_created_by():
    """تسجيل نزيلٍ جديد يحفظ اسم من سجّله (created_by)، عند الإنشاء فقط."""
    ROUTE = (ROOT / "routes/hotel_ops.py").read_text(encoding="utf-8")
    STORE = (ROOT / "db/store.py").read_text(encoding="utf-8")
    MIG = (ROOT / "db/schema_migrations.py").read_text(encoding="utf-8")
    assert 'data["created_by"] = actor_label(session)' in ROUTE
    assert "created_by" in STORE and "INSERT INTO guests" in STORE
    assert "ADD COLUMN IF NOT EXISTS created_by" in MIG
