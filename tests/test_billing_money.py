#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_billing_money.py — تحقّقٌ بالكسر لحساب المال (billing_money).

خالصٌ بلا قاعدة بيانات ولا fastapi: ضريبةٌ (جمعٌ/استخراجٌ ذهاباً وإياباً)،
تعدّد عملاتٍ (أسّ كل عملة والرجوع)، وبطاقاتٌ منتهيةٌ صحّةً وكذباً.
"""
from __future__ import annotations

import math

import pytest

from services import billing_money as bm


# ── ضريبة القيمة المضافة ─────────────────────────────────────────────

def test_add_vat_default_rate():
    r = bm.add_vat(100)
    assert r == {"base": 100.0, "vat": 15.0, "total": 115.0}


def test_add_vat_rounds_to_two_places():
    r = bm.add_vat(33.33)
    assert r["vat"] == 5.0          # 33.33 * 0.15 = 4.9995 → 5.00
    assert r["total"] == 38.33


def test_add_vat_custom_rate():
    r = bm.add_vat(200, rate=0.05)
    assert r == {"base": 200.0, "vat": 10.0, "total": 210.0}


def test_extract_vat_reverses_add_vat_round_trip():
    for base in (100, 33.33, 799.99, 1, 12345.67):
        total = bm.add_vat(base)["total"]
        back = bm.extract_vat(total)
        assert back["total"] == round(total, 2)
        # base المستخرَج يساوي الأصل تقريباً (ضمن قرش)
        assert abs(back["base"] - round(base, 2)) <= 0.01
        # المجاميع الداخلية متّسقة: base + vat == total
        assert round(back["base"] + back["vat"], 2) == back["total"]


def test_extract_vat_inclusive_total():
    # 115 شاملة 15% → أساسٌ 100 وضريبةٌ 15
    r = bm.extract_vat(115)
    assert r == {"base": 100.0, "vat": 15.0, "total": 115.0}


def test_add_vat_zero_is_allowed():
    assert bm.add_vat(0) == {"base": 0.0, "vat": 0.0, "total": 0.0}


@pytest.mark.parametrize("bad", [-1, -0.01, "abc", None, float("nan")])
def test_add_vat_rejects_bad_amount(bad):
    with pytest.raises(ValueError):
        bm.add_vat(bad)


@pytest.mark.parametrize("bad", [-1, -0.5, "x", float("nan")])
def test_add_vat_rejects_bad_rate(bad):
    with pytest.raises(ValueError):
        bm.add_vat(100, rate=bad)


@pytest.mark.parametrize("bad", [-1, "abc", None, float("nan")])
def test_extract_vat_rejects_bad_total(bad):
    with pytest.raises(ValueError):
        bm.extract_vat(bad)


# ── تعدّد العملات ────────────────────────────────────────────────────

@pytest.mark.parametrize("currency,exp", [
    ("SAR", 2), ("USD", 2), ("AED", 2), ("EGP", 2), ("QAR", 2), ("EUR", 2),
    ("JPY", 0),
    ("KWD", 3), ("BHD", 3), ("JOD", 3), ("OMR", 3),
])
def test_to_minor_each_exponent(currency, exp):
    assert bm.to_minor(1, currency) == 10 ** exp


def test_to_minor_examples():
    assert bm.to_minor(10.50, "SAR") == 1050      # هللات
    assert bm.to_minor(1000, "JPY") == 1000       # بلا كسور
    assert bm.to_minor(2.5, "KWD") == 2500        # ثلاث خانات
    assert bm.to_minor(9.999, "KWD") == 9999


def test_from_minor_each_exponent():
    assert bm.from_minor(1050, "SAR") == 10.50
    assert bm.from_minor(1000, "JPY") == 1000
    assert bm.from_minor(2500, "KWD") == 2.5


def test_minor_round_trip():
    for currency in ("SAR", "JPY", "KWD", "USD"):
        for major in (0, 1, 10.5, 99.99 if currency != "JPY" else 100):
            minor = bm.to_minor(major, currency)
            assert bm.from_minor(minor, currency) == round(
                float(major), bm._exp(currency))


def test_unknown_currency_falls_back_to_two_places():
    # عملةٌ مجهولة تُعامَل معاملة الريال (خانتان) لا تنفجر
    assert bm.to_minor(1, "XYZ") == 100
    assert bm.from_minor(100, "XYZ") == 1.0
    assert bm._exp("XYZ") == 2


def test_normalize_currency():
    assert bm.normalize_currency("sar") == "SAR"
    assert bm.normalize_currency(" usd ") == "USD"
    assert bm.normalize_currency("kwd") == "KWD"
    assert bm.normalize_currency("XYZ") == "SAR"   # مجهول → افتراضي
    assert bm.normalize_currency("") == "SAR"
    assert bm.normalize_currency(None) == "SAR"


def test_currency_table_matches_moyasar():
    # اتّساقٌ مع services/moyasar._CURRENCY_EXP — قاعدتان لنفس القرار تتباعدان
    moyasar = pytest.importorskip("services.moyasar")
    for code, exp in bm._CURRENCY_EXP.items():
        assert moyasar._CURRENCY_EXP.get(code) == exp


@pytest.mark.parametrize("bad", [-1, -0.01, "abc", None, float("nan")])
def test_to_minor_rejects_bad_amount(bad):
    with pytest.raises(ValueError):
        bm.to_minor(bad, "SAR")


@pytest.mark.parametrize("bad", [-1, "abc", None])
def test_from_minor_rejects_bad_amount(bad):
    with pytest.raises(ValueError):
        bm.from_minor(bad, "SAR")


# ── البطاقات المنتهية والرفض ─────────────────────────────────────────

@pytest.mark.parametrize("status,message", [
    ("failed", "expired_card"),
    ("failed", "expired"),
    ("declined", "card_expired"),
    ("expired", ""),
    ("failed", "Your card is expired"),
    ("failed", "EXPIRED CARD"),
    ("failed", "card-expired"),
])
def test_is_expired_card_true(status, message):
    assert bm.is_expired_card(status, message) is True


@pytest.mark.parametrize("status,message", [
    ("failed", "insufficient_funds"),
    ("declined", "do_not_honor"),
    ("failed", "invalid_cvc"),
    ("paid", ""),
    ("failed", ""),
    ("", ""),
    ("failed", "something weird"),
])
def test_is_expired_card_false(status, message):
    assert bm.is_expired_card(status, message) is False


@pytest.mark.parametrize("status,source,reason", [
    ("failed", "expired_card", "expired_card"),
    ("failed", "insufficient_funds", "insufficient_funds"),
    ("failed", "insufficient", "insufficient_funds"),
    ("declined", "declined", "declined"),
    ("failed", "card_declined", "declined"),
    ("failed", "do_not_honour", "declined"),
    ("failed", "invalid_cvc", "invalid_cvc"),
    ("failed", "incorrect_number", "invalid_card"),
    ("failed", "lost_card", "card_blocked"),
    ("failed", "stolen_card", "card_blocked"),
    ("failed", "3ds_failed", "authentication_failed"),
    ("failed", "timeout", "processing_error"),
])
def test_card_failure_reason_maps(status, source, reason):
    assert bm.card_failure_reason(status, source) == reason


def test_card_failure_reason_partial_match_in_message():
    assert bm.card_failure_reason(
        "failed", "The card was declined by the bank") == "declined"


def test_card_failure_reason_falls_back_to_status():
    # لا تفصيل → تُصنَّف الحالة نفسها
    assert bm.card_failure_reason("declined", "") == "declined"
    assert bm.card_failure_reason("expired", None) == "expired_card"


def test_card_failure_reason_unknown_is_stable():
    assert bm.card_failure_reason("failed", "gremlins") == "unknown"
    assert bm.card_failure_reason("", "") == "unknown"


def test_nan_guard_actually_triggers():
    # تأكيدٌ أنّ الحارس يكسر فعلاً على NaN (لا يمرّ صامتاً)
    assert math.isnan(float("nan"))
    with pytest.raises(ValueError):
        bm.to_minor(float("nan"), "SAR")
