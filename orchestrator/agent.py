#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/agent.py — حلقة الوكيل: نموذج → أداة → نتيجة → تكرار

حلقةٌ واحدةٌ يستعملها وكلاء الأدوار والوكيل الرئيسي: النموذج يطلب أداةً،
ننفّذها ونعيد نتيجتها، حتى ردٍّ نهائيٍّ بلا طلب أداة. كل خطوةٍ تُسجَّل في
`ActivityLog` — «خبرٌ بكل حركة». عميل النموذج يُحقَن فيُختبَر بلا شبكة.
"""
from __future__ import annotations

from typing import Any

from .activity import ActivityLog
from .dheuof import DheuofClient
from .roles import Role
from .tools import executors, schemas_for


def _blocks(resp: Any) -> list:
    """كتل الرد، سواءٌ كائناتُ SDK أو قواميس (للاختبار)."""
    return list(getattr(resp, "content", None) or (resp.get("content") if isinstance(resp, dict) else []))


def _bkind(b: Any) -> str:
    return getattr(b, "type", None) or (b.get("type") if isinstance(b, dict) else "")


def _battr(b: Any, name: str, default=None):
    return getattr(b, name, None) if not isinstance(b, dict) else b.get(name, default)


def _stop_reason(resp: Any) -> str:
    return getattr(resp, "stop_reason", None) or (resp.get("stop_reason") if isinstance(resp, dict) else "")


def _text_of(resp: Any) -> str:
    out = []
    for b in _blocks(resp):
        if _bkind(b) == "text":
            out.append(_battr(b, "text", "") or "")
    return "".join(out).strip()


def run_loop(*, llm: Any, model: str, max_tokens: int, system: str,
             tools: list, execs: dict, command: str,
             activity: ActivityLog, actor: str, max_steps: int) -> str:
    """يشغّل حلقة الأداة حتى ردٍّ نهائي أو نفاد الخطوات."""
    messages = [{"role": "user", "content": command}]
    for _ in range(max_steps):
        resp = llm.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            tools=tools, messages=messages,
        )
        messages.append({"role": "assistant", "content": _blocks(resp)})
        tool_uses = [b for b in _blocks(resp) if _bkind(b) == "tool_use"]
        if _stop_reason(resp) != "tool_use" or not tool_uses:
            text = _text_of(resp)
            activity.agent_reply(actor, text)
            return text
        results = []
        for tu in tool_uses:
            name = _battr(tu, "name", "")
            args = _battr(tu, "input", {}) or {}
            tuid = _battr(tu, "id", "")
            fn = execs.get(name)
            if not fn:
                results.append({"type": "tool_result", "tool_use_id": tuid,
                                "content": f"أداة غير معروفة: {name}", "is_error": True})
                continue
            try:
                out = fn(args)               # التنفيذ يُسجَّل داخل عميل ضيوف
                results.append({"type": "tool_result", "tool_use_id": tuid, "content": out})
            except Exception as exc:
                activity.error(actor, f"فشل الأداة {name}: {exc}")
                results.append({"type": "tool_result", "tool_use_id": tuid,
                                "content": f"خطأ: {exc}", "is_error": True})
        messages.append({"role": "user", "content": results})
    activity.error(actor, "نفدت خطوات الوكيل دون ردٍّ نهائي")
    return "لم يكتمل — نفدت خطوات الوكيل."


def run_role_agent(*, role: Role, task: str, dheuof: DheuofClient,
                   activity: ActivityLog, llm: Any, model: str,
                   max_tokens: int, max_steps: int) -> str:
    """يشغّل وكيل دورٍ واحدٍ بأدواته المسموحة على مهمّةٍ مفوَّضة."""
    activity.agent_start(role.key)
    return run_loop(
        llm=llm, model=model, max_tokens=max_tokens,
        system=role.instructions, tools=schemas_for(role.tools),
        execs=executors(dheuof, role.key), command=task,
        activity=activity, actor=role.key, max_steps=max_steps,
    )
