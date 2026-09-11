#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_integration_credentials.py — خزنة اعتمادات التكاملات لكل مشترك.

تحقّق بالكسر: لا يُخزَّن سرٌّ بلا تشفير · العرض مقنّعٌ بلا سرّ · الاسترجاع
يفكّ للاستخدام · العزل بين المنشآت · حذفٌ تحت تصرّف المشترك.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services import integration_credentials as vault  # noqa: E402


class _FakeDB:
    """قاعدة صوريّة بتخزينٍ فعليّ لصفوف integration_credentials."""
    use_postgres = True

    def __init__(self):
        self.rows = {}     # (client_id, service) -> dict

    def execute(self, q, p=None, fetch=None):
        if q.startswith("INSERT INTO integration_credentials"):
            self.rows[(p[0], p[1])] = {"secret_enc": p[2], "key_hint": p[3],
                                       "enabled": True, "updated_at": None}
            return {"ok": 1}
        if "SELECT secret_enc FROM integration_credentials" in q:
            r = self.rows.get((p[0], p[1]))
            return {"secret_enc": r["secret_enc"]} if r and r["enabled"] else None
        if "SELECT service, key_hint" in q:
            if len(p) == 2:
                r = self.rows.get((p[0], p[1]))
                items = [((p[0], p[1]), r)] if r else []
            else:
                items = [(k, v) for k, v in self.rows.items() if k[0] == p[0]]
            return [{"service": k[1], "key_hint": v["key_hint"],
                     "enabled": v["enabled"], "updated_at": None} for k, v in items]
        if q.startswith("DELETE FROM integration_credentials"):
            self.rows.pop((p[0], p[1]), None)
            return None
        return None


class _FakeCrypto:
    """تشفيرٌ صوريّ عكوسٌ (Base64-ish) لاختبار المسار دون مفتاح حقيقي."""
    enabled = True

    @staticmethod
    def is_enabled():
        return _FakeCrypto.enabled

    @staticmethod
    def encrypt(s):
        return "enc:" + s

    @staticmethod
    def decrypt(s):
        return s[4:] if s and s.startswith("enc:") else s


def _patch(monkeypatch, enabled=True):
    _FakeCrypto.enabled = enabled
    monkeypatch.setattr(vault, "guest_crypto", _FakeCrypto)


SECRET = {"api_key": "sk_live_abcdef123456"}


class TestSave:
    def test_refuses_without_encryption(self, monkeypatch):
        _patch(monkeypatch, enabled=False)
        res = vault.save(_FakeDB(), "h1", "booking", SECRET)
        assert res["persisted"] is False and res["error"] == "encryption_not_configured"

    def test_refuses_empty_secret(self, monkeypatch):
        _patch(monkeypatch)
        assert vault.save(_FakeDB(), "h1", "booking", {})["persisted"] is False

    def test_saves_encrypted_and_returns_masked(self, monkeypatch):
        _patch(monkeypatch)
        db = _FakeDB()
        res = vault.save(db, "h1", "booking", SECRET)
        assert res["persisted"] is True and res["connected"] is True
        # القناع لا يكشف المفتاح، والمخزَّن مشفّرٌ لا نصّ صريح
        assert "sk_live_abcdef123456" not in res["key_hint"]
        stored = db.rows[("h1", "booking")]["secret_enc"]
        assert stored.startswith("enc:") and "sk_live_abcdef123456" in _FakeCrypto.decrypt(stored)


class TestGetStatusDelete:
    def test_get_decrypts_for_use(self, monkeypatch):
        _patch(monkeypatch)
        db = _FakeDB()
        vault.save(db, "h1", "booking", SECRET)
        got = vault.get(db, "h1", "booking")
        assert got == SECRET            # مفكوكٌ للاستخدام في المحوّل

    def test_status_never_returns_secret(self, monkeypatch):
        _patch(monkeypatch)
        db = _FakeDB()
        vault.save(db, "h1", "booking", SECRET)
        st = vault.status(db, "h1")
        blob = json.dumps(st, ensure_ascii=False)
        assert "sk_live_abcdef123456" not in blob
        assert st[0]["service"] == "booking" and st[0]["connected"] is True

    def test_tenant_isolation(self, monkeypatch):
        _patch(monkeypatch)
        db = _FakeDB()
        vault.save(db, "h1", "booking", SECRET)
        assert vault.get(db, "h2", "booking") is None      # منشأة أخرى لا ترى
        assert vault.status(db, "h2") == []

    def test_delete_removes(self, monkeypatch):
        _patch(monkeypatch)
        db = _FakeDB()
        vault.save(db, "h1", "booking", SECRET)
        vault.delete(db, "h1", "booking")
        assert vault.get(db, "h1", "booking") is None
