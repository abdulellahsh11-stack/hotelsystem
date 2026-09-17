#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_admin_api_keys.py — تخصيص مفاتيح API للمنشأة من لوحة مالك المنصّة

رقم المنشأة (client_id) مسجَّلٌ في قاعدة البيانات، ومالك المنصّة وحده
يُصدر أو يُبطل مفتاح API مرتبطاً به. هنا نتحقّق أن المسارات موجودة،
محروسةٌ بـ`require_admin`، وأن دورة حياة المفتاح (إصدار → تدقيق →
إبطال) صحيحة بالكسر: مفتاحٌ مُبطَل لا يُدقَّق.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADMIN = ROOT / "routes/admin.py"
DASH = ROOT / "html_pages.py"


# ── المسارات موجودة ومحروسة بمالك المنصّة ───────────────────────
def test_the_three_api_key_routes_exist_and_require_admin():
    src = ADMIN.read_text(encoding="utf-8")
    wanted = [
        (r'@router\.get\("/api/admin/clients/\{client_id\}/api-keys"\)',),
        (r'@router\.post\("/api/admin/clients/\{client_id\}/api-keys"\)',),
        (r'@router\.post\("/api/admin/clients/\{client_id\}/api-keys/\{key_id\}/revoke"\)',),
    ]
    for (pat,) in wanted:
        m = re.search(pat + r"\s*\nasync def \w+\(([^)]*)\)", src)
        assert m, "مسار مفقود: %s" % pat
        assert "require_admin" in m.group(1), "مسار المفاتيح بلا حارس مالك المنصّة"


def test_admin_key_issue_binds_to_the_client_id():
    """المفتاح يُصدَر لرقم المنشأة تحديداً، لا عاماً."""
    src = ADMIN.read_text(encoding="utf-8")
    assert "mgr.issue_key(client_id" in src
    assert "mgr.revoke_key(client_id" in src


def test_admin_panel_wires_the_key_actions():
    """اللوحة تنادي الخادم فعلاً — لا زرٌّ صوريّ."""
    src = DASH.read_text(encoding="utf-8")
    assert "/api/admin/clients/'+cid+'/api-keys'" in src
    assert "loadApiKeys" in src and "issueApiKey" in src and "revokeApiKey" in src


# ── دورة الحياة بالكسر ──────────────────────────────────────────
class _FakeDB:
    """قاعدةٌ صوريّة صغيرة تكفي لدورة إصدار/تدقيق/إبطال."""
    use_postgres = True

    def __init__(self):
        self.rows = []
        self._id = 0

    def execute(self, q, p=None, fetch=None):
        nq = " ".join(q.split())
        if nq.startswith("CREATE TABLE") or nq.startswith("CREATE INDEX"):
            return None
        if nq.startswith("INSERT INTO api_keys"):
            self._id += 1
            cid, name, key_hash, key_hint, scopes = p
            self.rows.append({"id": self._id, "client_id": cid, "name": name,
                              "key_hash": key_hash, "key_hint": key_hint,
                              "scopes": scopes, "active": True})
            return None
        if nq.startswith("SELECT client_id, scopes, active FROM api_keys"):
            for r in self.rows:
                if r["key_hash"] == p[0]:
                    return dict(r)
            return None
        if nq.startswith("UPDATE api_keys SET last_used"):
            return None
        if nq.startswith("UPDATE api_keys SET active=FALSE"):
            kid, cid = p
            n = 0
            for r in self.rows:
                if r["id"] == kid and r["client_id"] == cid:
                    r["active"] = False
                    n += 1
            return n
        return None


def test_revoked_key_no_longer_validates():
    from services.api_keys import APIKeyManager

    db = _FakeDB()
    mgr = APIKeyManager(db)
    issued = mgr.issue_key("11223344", name="محاسبة", scopes=["rooms:read"])
    raw = issued["api_key"]
    assert mgr.validate_key(raw)["client_id"] == "11223344"   # صالح أولاً
    assert mgr.revoke_key("11223344", db.rows[0]["id"]) is True
    assert mgr.validate_key(raw) is None                      # بعد الإبطال: لا


def test_a_key_cannot_be_revoked_across_facilities():
    """منشأةٌ لا تُبطل مفتاح أخرى — العزل برقم المنشأة."""
    from services.api_keys import APIKeyManager

    db = _FakeDB()
    mgr = APIKeyManager(db)
    mgr.issue_key("11223344")
    assert mgr.revoke_key("99999999", db.rows[0]["id"]) is False
    # ما زال فعّالاً لمالكه
    assert db.rows[0]["active"] is True
