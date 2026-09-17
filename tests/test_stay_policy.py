#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_stay_policy.py — سياسة الدخول والخروج تُحفَظ فعلاً وبصلاحية

كان زرّ «حفظ السياسة» يُغلق النافذة ويعلن النجاح بلا نداء خادم — شيفرةٌ
تكذب. هنا نتحقّق أن المسارين موجودان، وأن الحفظ محروسٌ بمالك/مدير
المنشأة (`require_manager`)، وأن الواجهة تنادي الخادم لا تدّعي، وأن
التنقية ترفض المُدخَل الفاسد.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OPS = ROOT / "routes/hotel_ops.py"
JS = ROOT / "static/dheuof/modules/01-guests/js/registration-form.js"


# ── المساران موجودان، والحفظ محروسٌ بمالك/مدير المنشأة ───────────
def test_stay_policy_routes_exist_and_write_is_manager_guarded():
    src = OPS.read_text(encoding="utf-8")
    get_m = re.search(
        r'@router\.get\("/api/settings/stay-policy"\)\s*\nasync def \w+\(([^)]*)\)', src
    )
    post_m = re.search(
        r'@router\.post\("/api/settings/stay-policy"\)\s*\nasync def \w+\(([^)]*)\)', src
    )
    assert get_m, "مسار قراءة السياسة مفقود"
    assert post_m, "مسار حفظ السياسة مفقود"
    # الحفظ لمالك المنشأة ومديرها وحدهما
    assert "require_manager" in post_m.group(1), "حفظ السياسة بلا حارس المدير"


def test_stay_policy_binds_to_session_client_not_a_path_id():
    """العزل: السياسة تُقرأ وتُكتب لمنشأة الجلسة، لا لمعرّفٍ من الطلب."""
    src = OPS.read_text(encoding="utf-8")
    assert 'settings["stay_policy"] = policy' in src
    assert 'store.get_client(session["client_id"])' in src


# ── الواجهة تنادي الخادم — لا زرٌّ صوريّ ─────────────────────────
def test_panel_saves_to_server_not_a_fake_toast():
    src = JS.read_text(encoding="utf-8")
    assert "/api/settings/stay-policy" in src
    assert "function savePolicy" in src
    # النجاح يُعلَن بعد ردٍّ ناجح فقط، لا بمجرّد إغلاق النافذة
    m = re.search(r"function savePolicy\(\)\{.*?\n  \}", src, re.S)
    assert m, "savePolicy غير موجودة"
    assert "fetch(" in m.group(0), "savePolicy لا تنادي الخادم"


# ── التنقية ترفض الفاسد ─────────────────────────────────────────
def test_sanitize_rejects_bad_input():
    from services import stay_policy

    out = stay_policy.sanitize({
        "checkin_time": "25:99",          # وقتٌ غير صالح → افتراضي
        "checkout_time": "11:30",         # صالح → يُحفَظ
        "late_checkout_fee": "-5",        # سالب → افتراضي
        "late_checkout_block_hours": 0,   # < ١ → افتراضي
    })
    assert out["checkin_time"] == "14:00"
    assert out["checkout_time"] == "11:30"
    assert out["late_checkout_fee"] == 200
    assert out["late_checkout_block_hours"] == 3


def test_get_policy_merges_saved_over_defaults():
    from services import stay_policy

    p = stay_policy.get_policy({"settings": {"stay_policy": {"checkout_time": "10:00"}}})
    assert p["checkout_time"] == "10:00"      # المحفوظ
    assert p["checkin_time"] == "14:00"       # الافتراضي لِما لم يُحفَظ
