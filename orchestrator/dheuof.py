#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/dheuof.py — عميل واجهة ضيوف المفتوحة، مصادَقاً بمفتاح الاشتراك

كل نداءٍ للمنصّة يمرّ من هنا بمفتاح API الخاصّ بالاشتراك (dhk_…) على
ترويسة `X-API-Key`. العزل مضمونٌ من الخادم: المفتاح مرتبطٌ برقم المنشأة،
فلا يبلغ الطاقمُ بيانات اشتراكٍ آخر ولو حاول.

لا نداء بلا أثر: يُمرَّر `ActivityLog` فيُسجَّل كل طلبٍ ونتيجته.
"""
from __future__ import annotations

from typing import Any, Optional

from .activity import ActivityLog


class DheuofError(RuntimeError):
    pass


class DheuofClient:
    """عميلٌ رفيعٌ فوق واجهة `/api/open/v1` بمفتاح الاشتراك."""

    def __init__(self, base_url: str, api_key: str, subscription: str,
                 activity: Optional[ActivityLog] = None, http: Any = None):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.subscription = str(subscription)
        self.activity = activity
        self._http = http                 # يُحقَن للاختبار؛ وإلا httpx

    def _client(self):
        if self._http is not None:
            return self._http
        import httpx
        self._http = httpx.Client(timeout=30.0)
        return self._http

    def call(self, method: str, path: str, actor: str = "orchestrator",
             params: dict = None, json: dict = None) -> dict:
        """نداءٌ واحدٌ للمنصّة، مسجَّلٌ من الطلب إلى النتيجة."""
        url = f"{self.base}/api/open/v1/{path.lstrip('/')}"
        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        if self.activity:
            self.activity.tool_call(actor, f"{method} {path}",
                                    {"params": params or {}, "body": json or {}})
        try:
            resp = self._client().request(method, url, headers=headers,
                                          params=params, json=json)
            ok = 200 <= resp.status_code < 300
            try:
                body = resp.json()
            except Exception:
                body = {"raw": resp.text[:400]}
            if self.activity:
                summ = "نجح" if ok else f"HTTP {resp.status_code}: {str(body)[:160]}"
                self.activity.tool_result(actor, f"{method} {path}", ok, summ)
            if not ok:
                raise DheuofError(f"HTTP {resp.status_code}: {body}")
            return body
        except DheuofError:
            raise
        except Exception as exc:
            if self.activity:
                self.activity.error(actor, f"تعذّر نداء {path}: {exc}")
            raise DheuofError(str(exc)) from exc

    # ── نداءاتٌ جاهزة يستعملها الطاقم ─────────────────────────────
    def whoami(self, actor="orchestrator"):
        return self.call("GET", "me", actor)

    def rooms(self, actor="reception"):
        return self.call("GET", "rooms", actor)

    def availability(self, check_in="", check_out="", actor="reception"):
        return self.call("GET", "availability", actor,
                         params={"check_in": check_in, "check_out": check_out})

    def bookings(self, status="", actor="reception"):
        return self.call("GET", "bookings", actor, params={"status": status})

    def guests(self, actor="reception"):
        return self.call("GET", "guests", actor)

    def inventory(self, actor="housekeeping"):
        return self.call("GET", "inventory", actor)

    def accounting_summary(self, actor="accounting"):
        return self.call("GET", "accounting/summary", actor)

    def invoices(self, actor="accounting"):
        return self.call("GET", "invoices", actor)
