#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_security_headers_and_errors.py — رؤوس الأمان وإخفاء تفاصيل الخطأ

يحرس عيبين:
  ١) كان الخادم يرجع تفاصيل الاستثناء للعميل (`detail=…{str(e)}`) — تسريبٌ
     داخليٌّ هادئ. الآن الرسالة عامّة، والتفاصيل في السجلّ لا في الرد.
  ٢) نقص رؤوس CSP و HSTS. الآن تُضاف على كل رد (HSTS على HTTPS فقط).
"""
from __future__ import annotations

import re
import warnings
from pathlib import Path

from fastapi.testclient import TestClient

warnings.filterwarnings("ignore")

from main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
client = TestClient(app)


# ── ١) لا تُسرَّب تفاصيل الاستثناء للعميل ───────────────────────
def test_no_route_leaks_exception_text_to_client():
    """لا مسارٌ يرجع {str(e)} في detail — التفاصيل للسجلّ لا للعميل."""
    leaks = []
    for path in (ROOT / "routes").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        if re.search(r'detail=f?"[^"]*\{str\(e\)\}', src):
            leaks.append(path.name)
    assert not leaks, f"تسريب تفاصيل الخطأ في: {leaks}"


def test_server_error_body_is_generic():
    """رسالة خطأ الخادم عامّةٌ لا تكشف الداخل."""
    # مسارٌ غير موجود يرجع 404 بجسمٍ لا يحوي أثراً برمجياً
    r = client.get("/api/definitely-not-a-real-endpoint-xyz")
    assert r.status_code in (404, 401, 403)
    assert "Traceback" not in r.text


# ── ٢) رؤوس الأمان حاضرة ────────────────────────────────────────
def test_core_security_headers_present():
    r = client.get("/")
    for h in ("X-Content-Type-Options", "X-Frame-Options",
              "Referrer-Policy", "Content-Security-Policy"):
        assert h in r.headers, f"رأس الأمان مفقود: {h}"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "object-src 'none'" in r.headers["Content-Security-Policy"]


def test_hsts_present_behind_https_proxy():
    """HSTS يُضاف عندما يُعلن الوسيط أن الأصل HTTPS."""
    r = client.get("/", headers={"x-forwarded-proto": "https"})
    assert "Strict-Transport-Security" in r.headers
    assert "max-age=" in r.headers["Strict-Transport-Security"]


def test_hsts_absent_on_plain_http():
    """لا نفرض HSTS على http المحلي حتى لا نقفل التطوير.
    نثبّت المضيف على localhost حتى لا يتدخّل تحويل HTTPS للمضيف العام."""
    r = client.get("/", headers={"x-forwarded-proto": "http", "host": "localhost"},
                   follow_redirects=False)
    assert "Strict-Transport-Security" not in r.headers
