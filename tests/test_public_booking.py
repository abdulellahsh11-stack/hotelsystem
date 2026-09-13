#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_public_booking.py — API الحجز المباشر العامّ.

تحقّق بالكسر: تواريخ · سعة · تسعير+ضريبة · تداخل · وإدراجٌ محروسٌ بعدم
Overbooking وإيديمبوتنسي عبر FakeDB على المسار.
"""
import os
import sys
from datetime import date

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import public_booking as pb  # noqa: E402

TODAY = date(2026, 6, 1)


class TestPureLogic:
    def test_parse_stay_ok(self):
        ci, co, n = pb.parse_stay("2026-10-10", "2026-10-13", today=TODAY)
        assert (ci, co, n) == (date(2026, 10, 10), date(2026, 10, 13), 3)

    def test_parse_rejects_past_and_reversed(self):
        with pytest.raises(pb.BookingError):
            pb.parse_stay("2026-05-01", "2026-05-03", today=TODAY)
        with pytest.raises(pb.BookingError):
            pb.parse_stay("2026-10-10", "2026-10-10", today=TODAY)

    def test_guests_within_capacity(self):
        assert pb.validate_guests(2, 4) == 2
        with pytest.raises(pb.BookingError):
            pb.validate_guests(5, 4)

    def test_quote_price_plus_vat(self):
        q = pb.quote(400, nights=3)          # 1200 + 15%
        assert q["subtotal"] == 1200.0 and q["vat"] == 180.0 and q["total"] == 1380.0

    def test_quote_rejects_unpriced(self):
        with pytest.raises(pb.BookingError):
            pb.quote(0, nights=2)

    def test_overlaps(self):
        d = date
        assert pb.overlaps(d(2026,6,10), d(2026,6,13), d(2026,6,12), d(2026,6,15)) is True
        # مغادرةٌ يومَ وصولِ التالي لا تتداخل
        assert pb.overlaps(d(2026,6,10), d(2026,6,13), d(2026,6,13), d(2026,6,15)) is False


# ── اختبار المسار عبر FakeDB ─────────────────────────────────────────

class _FakeDB:
    use_postgres = True

    def __init__(self, published=True):
        self.published = published
        self.bookings = []          # (client_id, listing_id, ci, co, status, idem)
        self.by_idem = {}

    def execute(self, q, p=None, fetch=None):
        if "FROM listings l JOIN property_profile p" in q and "SELECT l.base_price" in q:
            return ({"base_price": 400, "weekend_price": None, "capacity": 4,
                     "min_nights": 1} if self.published else None)
        if q.startswith("SELECT id, status FROM public_bookings WHERE idempotency_key"):
            return self.by_idem.get(p[0])
        if "INSERT INTO public_bookings" in q:
            cid, listing_id = p[1], p[2]
            new_ci, new_co, idem = p[6], p[7], p[14]
            g_cid, g_lid, g_co, g_ci = p[15], p[16], p[17], p[18]
            # حارس عدم التداخل (NOT EXISTS)
            for (bc, bl, bci, bco, st, _) in self.bookings:
                if bc == g_cid and bl == g_lid and st in ("confirmed", "pending_payment") \
                        and bci < g_co and bco > g_ci:
                    return None      # تداخل → لا إدراج
            self.bookings.append((cid, listing_id, new_ci, new_co, "confirmed", idem))
            self.by_idem[idem] = {"id": p[0], "status": "confirmed"}
            return {"id": p[0], "status": "confirmed", "total": p[13]}
        return None


class _Req:
    def __init__(self, db, body):
        self._body = body
        self.app = type("A", (), {"state": type("S", (), {"db": db})()})()

    async def json(self):
        return self._body


def _reserve(db, body):
    import asyncio
    from routes.public_booking import reserve
    return asyncio.get_event_loop().run_until_complete(reserve(_Req(db, body)))


BASE = {"client_id": "h1", "unit_id": 5, "guest_name": "زائر", "guest_phone": "0500000000",
        "check_in": "2026-10-10", "check_out": "2026-10-13", "guests_count": 2}


class TestReserve:
    def test_direct_booking_confirmed(self):
        res = _reserve(_FakeDB(), dict(BASE))
        assert res["success"] and res["data"]["status"] == "confirmed"
        assert res["data"]["total"] == 1380.0

    def test_overbooking_blocked(self):
        db = _FakeDB()
        _reserve(db, dict(BASE, guest_phone="0500000001"))
        with pytest.raises(HTTPException) as e:      # مدّة متداخلة، جوال مختلف
            _reserve(db, dict(BASE, check_in="2026-10-12", check_out="2026-10-14",
                              guest_phone="0500000002"))
        assert e.value.status_code == 409

    def test_idempotency_returns_same(self):
        db = _FakeDB()
        r1 = _reserve(db, dict(BASE, idempotency_key="k1"))
        r2 = _reserve(db, dict(BASE, idempotency_key="k1"))
        assert r2.get("duplicate") is True and r2["data"]["id"] == r1["data"]["id"]
        assert len(db.bookings) == 1

    def test_unpublished_unit_404(self):
        with pytest.raises(HTTPException) as e:
            _reserve(_FakeDB(published=False), dict(BASE))
        assert e.value.status_code == 404

    def test_missing_contact_400(self):
        with pytest.raises(HTTPException) as e:
            _reserve(_FakeDB(), dict(BASE, guest_phone=""))
        assert e.value.status_code == 400

    def test_non_overlapping_second_booking_ok(self):
        db = _FakeDB()
        _reserve(db, dict(BASE, guest_phone="0500000001"))
        r = _reserve(db, dict(BASE, check_in="2026-10-13", check_out="2026-10-15",
                              guest_phone="0500000003"))
        assert r["success"] and len(db.bookings) == 2
