#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_launch_readiness.py — بنود جاهزية الإطلاق البرمجية

يحرس: أيقونة الموقع · صورة المعاينة · صفحة 404 مخصّصة · تحويل HTTPS ·
شريط الكوكيز · الصفحات القانونية · روابط الفوتر · حقن التحليلات المشروط.
"""
from __future__ import annotations

import os
import warnings

from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from main import app  # noqa: E402

client = TestClient(app)


# ── الأصول ──────────────────────────────────────────────────────
def test_favicon_served():
    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "")


def test_favicon_ico_redirects_to_svg():
    r = client.get("/favicon.ico", follow_redirects=False)
    assert r.status_code in (301, 302, 307, 308)
    assert r.headers["location"] == "/favicon.svg"


def test_og_image_served():
    r = client.get("/og-image.png")
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/")


# ── الصفحات القانونية ───────────────────────────────────────────
def test_privacy_and_terms_pages():
    for path, marker in (("/privacy", "الخصوصية"), ("/terms", "الشروط")):
        r = client.get(path)
        assert r.status_code == 200
        assert marker in r.text


def test_legal_pages_in_sitemap():
    r = client.get("/sitemap.xml")
    assert "/privacy" in r.text and "/terms" in r.text


# ── صفحة 404 مخصّصة ────────────────────────────────────────────
def test_custom_404_for_pages():
    r = client.get("/this-page-does-not-exist-xyz")
    assert r.status_code == 404
    assert "404" in r.text and "الرئيسية" in r.text


def test_api_404_stays_json():
    r = client.get("/api/nope-not-here-xyz")
    assert r.status_code == 404
    assert "الرئيسية" not in r.text  # ليست صفحة HTML


# ── تحويل HTTPS ─────────────────────────────────────────────────
def test_https_redirect_behind_proxy():
    # خلف وسيطٍ يعلن http على مضيفٍ غير محلّي → تحويل 308 إلى https
    r = client.get("/", headers={"x-forwarded-proto": "http", "host": "dheuof.com"},
                   follow_redirects=False)
    assert r.status_code == 308
    assert r.headers["location"].startswith("https://")


def test_no_redirect_on_localhost():
    r = client.get("/", headers={"x-forwarded-proto": "http", "host": "localhost"},
                   follow_redirects=False)
    # مضيفٌ محلّي حتى مع إعلان http → لا تحويل (حتى لا يُقفل التطوير)
    assert r.status_code != 308


def test_no_redirect_without_proxy_header():
    # طلبٌ مباشر بلا x-forwarded-proto → لا تحويل (لا نستنتج من scheme)
    r = client.get("/favicon.svg", follow_redirects=False)
    assert r.status_code == 200


# ── الموقع التسويقي: كوكيز + روابط قانونية + تحليلات مشروطة ─────
def test_marketing_has_cookie_bar_and_legal_links():
    r = client.get("/", headers={"host": "dheuof.com", "x-forwarded-proto": "https"})
    assert r.status_code == 200
    assert "cookieBar" in r.text
    assert "/privacy" in r.text and "/terms" in r.text


def test_analytics_absent_without_env():
    # بلا GA_MEASUREMENT_ID لا يُحقن أي gtag
    os.environ.pop("GA_MEASUREMENT_ID", None)
    r = client.get("/", headers={"host": "dheuof.com", "x-forwarded-proto": "https"})
    assert "googletagmanager.com/gtag" not in r.text


def test_analytics_injected_with_valid_env():
    os.environ["GA_MEASUREMENT_ID"] = "G-TEST1234"
    try:
        r = client.get("/", headers={"host": "dheuof.com", "x-forwarded-proto": "https"})
        assert "googletagmanager.com/gtag/js?id=G-TEST1234" in r.text
    finally:
        os.environ.pop("GA_MEASUREMENT_ID", None)


def test_analytics_rejects_bad_env():
    os.environ["GA_MEASUREMENT_ID"] = "not-a-valid-id'; alert(1)"
    try:
        r = client.get("/", headers={"host": "dheuof.com", "x-forwarded-proto": "https"})
        assert "alert(1)" not in r.text
        assert "gtag/js" not in r.text
    finally:
        os.environ.pop("GA_MEASUREMENT_ID", None)
