#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_room_map.py — خريطة الغرف: التخصيص والصلاحيات

مسارات الغرف كانت مفتوحةً لأي جلسة: موظف نظافة يحذف غرفة، وكاشير يغيّر
سعرها. الجلسة تُثبت **من** أنت لا **ماذا يحقّ لك**.

والخريطة كانت تشتقّ أسماء الأدوار من رقمٍ فقط، فلا تُسمّى «جناح الأمراء»
ولا يُخفى دورٌ تحت الصيانة.
"""
from __future__ import annotations

import warnings
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from app_core import _client_sessions, _lock  # noqa: E402
from main import app  # noqa: E402
from services.staff_roles import permissions_for  # noqa: E402

A, B = "hotel_A", "hotel_B"


class MapDB:
    use_postgres = True

    def __init__(self):
        self.rooms = [
            {"id": 1, "client_id": A, "room_number": "101", "room_type": "standard",
             "floor": 1, "capacity": 2, "base_price": 400, "status": "available", "notes": ""},
            {"id": 2, "client_id": A, "room_number": "102", "room_type": "standard",
             "floor": 1, "capacity": 2, "base_price": 400, "status": "occupied", "notes": ""},
            {"id": 3, "client_id": A, "room_number": "301", "room_type": "suite",
             "floor": 3, "capacity": 4, "base_price": 900, "status": "available", "notes": ""},
            {"id": 9, "client_id": B, "room_number": "999", "room_type": "suite",
             "floor": 9, "capacity": 2, "base_price": 1, "status": "available", "notes": ""},
        ]
        self.prefs: list[dict] = []

    def health(self):
        return {"ok": True}

    def execute(self, sql, params=(), fetch=None):
        low = " ".join(sql.split()).lower()
        p = tuple(params or ())

        if low.startswith("select id, room_number") and "from rooms" in low:
            return [dict(r) for r in self.rooms if r["client_id"] == p[0]]

        if "from room_map_floors" in low:
            return [dict(r) for r in self.prefs if r["client_id"] == p[0]]

        if low.startswith("insert into room_map_floors"):
            cid, floor, label, order, hidden = p
            existing = next((r for r in self.prefs
                             if r["client_id"] == cid and r["floor"] == floor), None)
            row = {"client_id": cid, "floor": floor, "label": label,
                   "sort_order": order, "is_hidden": hidden}
            if existing:
                existing.update(row)
            else:
                self.prefs.append(row)
            return 1

        if low.startswith("update rooms set status"):
            status, rid, cid = p
            for r in self.rooms:
                if r["id"] == rid and r["client_id"] == cid:
                    r["status"] = status
                    return 1
            return 0

        return None if fetch == "one" else []


@pytest.fixture
def client():
    app.state.db = MapDB()

    class _Cfg:
        pass_salt = "s"
        admin_pass_hash = ""
        owner_client_id = ""

    app.state.cfg = _Cfg()
    now = datetime.now().isoformat()
    with _lock:
        _client_sessions.clear()
        for token, cid in (("owner", A), ("bOwner", B)):
            _client_sessions[token] = {"client_id": cid, "role": "owner",
                                       "permissions": ["*"], "created_at": now}
        for token, role in (("recep", "receptionist"), ("hk", "housekeeping"),
                            ("acct", "accountant"), ("cashier", "pos_cashier")):
            _client_sessions[token] = {"client_id": A, "role": role,
                                       "permissions": permissions_for(role),
                                       "created_at": now}
    yield TestClient(app, raise_server_exceptions=False), app.state.db
    with _lock:
        _client_sessions.clear()


OWNER = {"client_token": "owner"}


def _map(c, cookies=OWNER):
    return c.get("/api/rooms/map", cookies=cookies)


# ── الخريطة تُبنى من الغرف الحقيقية ────────────────────────────
def test_the_map_is_built_from_real_rooms(client):
    c, _ = client
    data = _map(c).json()["data"]
    assert [f["floor"] for f in data["floors"]] == [1, 3]
    assert data["total_rooms"] == 3          # غرفة المنشأة الأخرى ليست منها


def test_rooms_are_grouped_under_their_floor(client):
    c, _ = client
    floors = _map(c).json()["data"]["floors"]
    assert [r["room_number"] for r in floors[0]["rooms"]] == ["101", "102"]
    assert [r["room_number"] for r in floors[1]["rooms"]] == ["301"]


def test_a_floor_without_customization_gets_a_derived_name(client):
    """الغياب يعني «الافتراضي» لا «مخفي»."""
    c, _ = client
    floors = _map(c).json()["data"]["floors"]
    assert floors[0]["label"] == "الدور 1"
    assert floors[0]["customized"] is False


# ── التخصيص ────────────────────────────────────────────────────
def _customize(c, floors, cookies=OWNER):
    return c.put("/api/rooms/map/floors", json={"floors": floors}, cookies=cookies)


def test_a_floor_can_be_renamed(client):
    c, _ = client
    assert _customize(c, [{"floor": 3, "label": "جناح الأمراء"}]).status_code == 200
    floors = _map(c).json()["data"]["floors"]
    named = next(f for f in floors if f["floor"] == 3)
    assert named["label"] == "جناح الأمراء"
    assert named["customized"] is True


def test_the_order_can_be_changed(client):
    """المنشأة قد تريد أدوارها بترتيبٍ غير العددي."""
    c, _ = client
    _customize(c, [{"floor": 1, "sort_order": 20}, {"floor": 3, "sort_order": 1}])
    assert [f["floor"] for f in _map(c).json()["data"]["floors"]] == [3, 1]


def test_a_floor_can_be_hidden_from_the_map(client):
    c, _ = client
    _customize(c, [{"floor": 1, "is_hidden": True}])
    data = _map(c).json()["data"]
    assert [f["floor"] for f in data["floors"]] == [3]
    assert data["hidden_count"] == 1


def test_hiding_a_floor_does_not_delete_its_rooms(client):
    """الإخفاء عرضٌ لا حذف: الغرف تبقى تُحجز وتُحاسَب."""
    c, db = client
    _customize(c, [{"floor": 1, "is_hidden": True}])
    assert len([r for r in db.rooms if r["client_id"] == A]) == 3


def test_customization_can_be_updated_not_duplicated(client):
    c, db = client
    _customize(c, [{"floor": 1, "label": "الأول"}])
    _customize(c, [{"floor": 1, "label": "المعدَّل"}])
    assert len([p for p in db.prefs if p["client_id"] == A]) == 1
    assert next(f for f in _map(c).json()["data"]["floors"]
                if f["floor"] == 1)["label"] == "المعدَّل"


def test_a_long_label_is_trimmed_not_rejected(client):
    c, db = client
    _customize(c, [{"floor": 1, "label": "ط" * 500}])
    assert len(db.prefs[0]["label"]) <= 80


@pytest.mark.parametrize("bad", [{"floors": "نص"}, {"floors": {"a": 1}}, {}])
def test_malformed_customization_is_refused(client, bad):
    c, _ = client
    assert c.put("/api/rooms/map/floors", json=bad, cookies=OWNER).status_code == 400


def test_a_non_numeric_floor_is_refused(client):
    c, _ = client
    assert _customize(c, [{"floor": "الأرضي"}]).status_code == 400


# ── الصلاحيات ──────────────────────────────────────────────────
@pytest.mark.parametrize("token", ["owner", "recep", "hk"])
def test_anyone_with_rooms_read_can_view_the_map(client, token):
    """الإشراف الداخلي يرى الخريطة — عملُه كلّه فيها."""
    c, _ = client
    assert _map(c, {"client_token": token}).status_code == 200


@pytest.mark.parametrize("token", ["acct", "cashier"])
def test_roles_without_rooms_read_are_refused(client, token):
    c, _ = client
    assert _map(c, {"client_token": token}).status_code == 403


@pytest.mark.parametrize("token", ["recep", "hk", "acct", "cashier"])
def test_only_a_writer_may_customize_the_map(client, token):
    """تسمية الأدوار قرارُ إدارة لا قرارُ من يقرأ الخريطة."""
    c, db = client
    r = _customize(c, [{"floor": 1, "label": "مخترَق"}], {"client_token": token})
    assert r.status_code == 403
    assert db.prefs == [], "حُفظ تخصيصٌ رغم رفض الصلاحية"


def test_the_map_tells_the_client_whether_it_may_edit(client):
    """الواجهة تُخفي أزرار التعديل بناءً على هذا — لا على تخمينها."""
    c, _ = client
    assert _map(c, OWNER).json()["data"]["can_edit"] is True
    assert _map(c, {"client_token": "hk"}).json()["data"]["can_edit"] is False


# ── تغيير الحالة من الخريطة ────────────────────────────────────
def test_a_writer_can_change_a_room_status(client):
    c, db = client
    # حالةٌ معتمدة تُخزَّن كما هي
    r = c.patch("/api/rooms/1/status", json={"status": "cleaning"}, cookies=OWNER)
    assert r.status_code == 200
    assert next(x for x in db.rooms if x["id"] == 1)["status"] == "cleaning"


def test_legacy_status_is_normalized_not_stored_verbatim(client):
    """المسمّى القديم `dirty` يُقبَل لكن يُخزَّن «cleaning» المعتمد —
    مفردةٌ واحدة لا مسمّيان لنفس الحالة."""
    c, db = client
    r = c.patch("/api/rooms/1/status", json={"status": "dirty"}, cookies=OWNER)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "cleaning"
    assert next(x for x in db.rooms if x["id"] == 1)["status"] == "cleaning"


@pytest.mark.parametrize("token", ["recep", "hk", "acct"])
def test_a_reader_cannot_change_a_room_status(client, token):
    c, db = client
    r = c.patch("/api/rooms/1/status", json={"status": "dirty"},
                cookies={"client_token": token})
    assert r.status_code == 403
    assert next(x for x in db.rooms if x["id"] == 1)["status"] == "available"


def test_an_unknown_status_is_refused(client):
    c, _ = client
    assert c.patch("/api/rooms/1/status", json={"status": "ممتازة"},
                   cookies=OWNER).status_code == 400


# ── العزل ──────────────────────────────────────────────────────
def test_the_map_never_crosses_tenants(client):
    c, _ = client
    other = _map(c, {"client_token": "bOwner"}).json()["data"]
    assert [f["floor"] for f in other["floors"]] == [9]


def test_customizing_does_not_touch_another_tenant(client):
    c, db = client
    _customize(c, [{"floor": 9, "label": "مدسوس"}], OWNER)
    assert all(p["client_id"] == A for p in db.prefs)
    assert next(f for f in _map(c, {"client_token": "bOwner"}).json()["data"]["floors"]
                if f["floor"] == 9)["label"] == "الدور 9"


def test_a_status_change_cannot_reach_another_tenant(client):
    c, db = client
    r = c.patch("/api/rooms/9/status", json={"status": "blocked"}, cookies=OWNER)
    assert r.status_code == 404
    assert next(x for x in db.rooms if x["id"] == 9)["status"] == "available"


def test_the_map_requires_a_session(client):
    c, _ = client
    assert c.get("/api/rooms/map").status_code in (401, 403)


# ── حارسٌ شامل: لا مسار غرفٍ بلا صلاحية ────────────────────────
def test_every_room_route_declares_a_permission():
    """
    الحارس الذي كان ناقصاً.

    حرستُ المسارات الجديدة وفاتتني `POST /api/rooms` و`/bulk` و`DELETE`
    — فبقي موظف النظافة قادراً على حذف غرفة. فحصُ مسارٍ مسارٍ يدوياً
    يُخطئ؛ هذا يفحصها كلها، ويفشل تلقائياً عند إضافة مسارٍ جديد بلا حارس.
    """
    import inspect
    import re

    import routes.hotel_ops as mod

    source = inspect.getsource(mod)
    unguarded = []
    for m in re.finditer(
            r'@router\.(get|post|put|patch|delete)\("(/api/rooms[^"]*)"\)'
            r'(?P<body>.*?)(?=\n@router\.|\Z)', source, re.S):
        if '_require(session,' not in m.group("body"):
            unguarded.append(f"{m.group(1).upper()} {m.group(2)}")
    assert not unguarded, "مسارات غرفٍ بلا فحص صلاحية: " + " · ".join(unguarded)


@pytest.mark.parametrize("token", ["hk", "acct", "cashier"])
def test_a_reader_cannot_delete_a_room(client, token):
    """سؤال المستخدم بالضبط: هل يستطيع من لا يملك الكتابة حذف غرفة؟"""
    c, _ = client
    r = c.delete("/api/rooms/1", cookies={"client_token": token})
    assert r.status_code == 403, f"{token} حذف غرفة بلا صلاحية ({r.status_code})"


@pytest.mark.parametrize("token", ["hk", "acct", "cashier"])
def test_a_reader_cannot_create_rooms(client, token):
    c, _ = client
    single = c.post("/api/rooms", json={"room_number": "X-1"},
                    cookies={"client_token": token})
    bulk = c.post("/api/rooms/bulk", json={"floors": 1, "rooms_per_floor": 1},
                  cookies={"client_token": token})
    assert single.status_code == 403 and bulk.status_code == 403
