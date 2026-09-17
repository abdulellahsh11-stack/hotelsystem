#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_orchestrator.py — طاقمُ الاشتراك: التوزيع، والأداة، و«خبرٌ بكل حركة»

بلا شبكة: نحقن نموذجاً صوريّاً (FakeLLM) وعميل HTTP صوريّاً. نتحقّق أن
الوكيل الرئيسي يفوّض لوكيل الدور، وأن الأداة تنادي واجهة ضيوف بمفتاح
الاشتراك، وأن كل حركةٍ تُسجَّل من الأمر إلى الرد.
"""
import json
import types
from pathlib import Path

import pytest

from orchestrator.config import Settings
from orchestrator import activity as act
from orchestrator.roles import ROLES
from orchestrator.tools import schemas_for


# ── كتل رد صوريّة تحاكي كائنات SDK ───────────────────────────────
def _text_block(t):
    return types.SimpleNamespace(type="text", text=t)


def _tool_block(name, args, tid="t1"):
    return types.SimpleNamespace(type="tool_use", name=name, input=args, id=tid)


def _resp(blocks, stop):
    return types.SimpleNamespace(content=blocks, stop_reason=stop)


def _ran_a_tool(messages):
    for m in messages:
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    return True
    return False


class FakeLLM:
    """نموذجٌ صوريّ: الوكيل الرئيسي يفوّض، ووكيل الدور ينادي أداةً ثم يجيب."""

    def __init__(self):
        self.calls = []
        self.messages = types.SimpleNamespace(create=self._create)

    def _create(self, model, max_tokens, system, tools, messages):
        names = [t["name"] for t in tools]
        self.calls.append(names)
        ran = _ran_a_tool(messages)
        if "delegate" in names:            # سياق الوكيل الرئيسي
            if not ran:
                return _resp([_tool_block("delegate",
                             {"role": "reception", "task": "كم غرفة متاحة؟"})], "tool_use")
            return _resp([_text_block("تم: ٣ غرف متاحة اليوم.")], "end_turn")
        if "get_rooms" in names:           # سياق وكيل الاستقبال
            if not ran:
                return _resp([_tool_block("get_rooms", {})], "tool_use")
            return _resp([_text_block("يوجد ٣ غرف متاحة.")], "end_turn")
        return _resp([_text_block("لا شيء")], "end_turn")


class FakeHTTP:
    """عميل HTTP صوريّ: يلتقط الترويسات ويعيد غرفاً."""

    def __init__(self):
        self.seen = []

    def request(self, method, url, headers=None, params=None, json=None):
        self.seen.append({"method": method, "url": url, "headers": headers or {}})
        body = {"success": True, "data": [{"room_number": "101", "status": "available"}]}
        return types.SimpleNamespace(status_code=200, json=lambda: body, text="")


def _settings(tmp_path):
    return Settings(subscription="11223344", dheuof_api_key="dhk_test",
                    dheuof_base_url="http://x", model="claude-opus-5",
                    activity_dir=str(tmp_path / "act"))


# ── التخصيص: كل دورٍ بأدواته ─────────────────────────────────────
def test_roles_are_scoped_not_general_purpose():
    assert set(ROLES) == {"reception", "housekeeping", "maintenance", "accounting"}
    # المحاسبة لا تلمس الغرف، والتنظيف لا يرى الفواتير
    assert "get_invoices" not in ROLES["housekeeping"].tools
    assert "get_rooms" not in ROLES["accounting"].tools
    assert [s["name"] for s in schemas_for(ROLES["reception"].tools)]


def test_config_requires_subscription_and_key():
    with pytest.raises(ValueError):
        Settings(subscription="", dheuof_api_key="k").require()
    with pytest.raises(ValueError):
        Settings(subscription="1", dheuof_api_key="").require()


# ── التوزيع + الأداة + المفتاح ───────────────────────────────────
def test_orchestrator_delegates_and_calls_api_with_subscription_key(tmp_path):
    from orchestrator.team import Team

    http = FakeHTTP()
    team = Team(_settings(tmp_path), llm=FakeLLM(), listener=None, http=http)
    assert team.number == "11223344"        # رقم الطاقم = رقم الاشتراك

    final = team.command("كم غرفة متاحة اليوم؟")
    assert "٣ غرف" in final

    # الأداة نادت واجهة ضيوف بمفتاح الاشتراك على الترويسة
    assert http.seen, "لم يُنادَ الخادم"
    assert http.seen[0]["headers"].get("X-API-Key") == "dhk_test"
    assert "/api/open/v1/rooms" in http.seen[0]["url"]


# ── «خبرٌ بكل حركة»: السجلّ كامل ─────────────────────────────────
def test_every_action_is_logged_and_persisted(tmp_path):
    from orchestrator.team import Team

    team = Team(_settings(tmp_path), llm=FakeLLM(), listener=None, http=FakeHTTP())
    team.command("كم غرفة متاحة اليوم؟")

    kinds = [e["kind"] for e in team.activity_log()]
    for expected in (act.COMMAND, act.DELEGATE, act.AGENT_START,
                     act.TOOL_CALL, act.TOOL_RESULT, act.AGENT_REPLY, act.RESULT):
        assert expected in kinds, f"حركة مفقودة من السجلّ: {expected}"

    # نداء الأداة يحمل الفاعل (وكيل الاستقبال) والأداة الفعلية
    tool_calls = [e for e in team.activity_log() if e["kind"] == act.TOOL_CALL]
    assert any(e["actor"] == "reception" for e in tool_calls)

    # السجلّ مكتوبٌ على القرص (JSONL) للمساءلة
    p = Path(tmp_path / "act" / "team_11223344.jsonl")
    assert p.exists()
    lines = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == len(team.activity_log())
    assert lines[0]["kind"] == act.COMMAND
