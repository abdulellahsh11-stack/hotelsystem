#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/orchestrator.py — الوكيل الرئيسي: يوزّع أوامر المالك على الطاقم

الوكيل الرئيسي لا ينفّذ بنفسه، بل يفوّض. أداتُه الوحيدة `delegate`: يختار
الدور الأنسب (استقبال/تنظيف/صيانة/محاسبة) ويعطيه مهمّةً، فيشغَّل وكيل
الدور بأدواته ويعيد نتيجته. يكرّر حتى يجمع ما يكفي لردٍّ نهائيٍّ للمالك.

كل تفويضٍ ونداءٍ يُسجَّل — المالك يرى الحركة كاملةً، من الأمر إلى الرد.
"""
from __future__ import annotations

from typing import Any

from .activity import ActivityLog
from .agent import run_loop, run_role_agent
from .config import Settings
from .dheuof import DheuofClient
from .roles import ROLES


def _delegate_schema() -> list:
    return [{
        "name": "delegate",
        "description": (
            "فوّض مهمّةً إلى أحد وكلاء الطاقم. اختر الدور الأنسب: "
            "reception (حجوزات/نزلاء/غرف)، housekeeping (حالة الغرف/مخزون)، "
            "maintenance (أعطال الصيانة)، accounting (فواتير/مالية)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {"type": "string", "enum": list(ROLES.keys())},
                "task": {"type": "string", "description": "المهمّة بالعربية"},
            },
            "required": ["role", "task"],
            "additionalProperties": False,
        },
    }]


_SYSTEM = (
    "أنت الوكيل الرئيسي لطاقم منشأةٍ فندقية في منصّة ضيوف. لا تنفّذ بنفسك: "
    "حلّل أمر المالك، وفوّض كل جزءٍ للدور الأنسب عبر أداة `delegate`. يمكنك "
    "التفويض أكثر من مرّة. عند اكتمال المعلومات، اكتب ردّاً نهائياً موجزاً "
    "بالعربية يلخّص ما فعله الطاقم ونتيجته. لا تخترع بيانات — اعتمد على ردود "
    "الوكلاء."
)


class Orchestrator:
    """طاقمُ اشتراكٍ واحد يقوده وكيلٌ رئيسي."""

    def __init__(self, settings: Settings, activity: ActivityLog,
                 dheuof: DheuofClient, llm: Any):
        self.s = settings
        self.activity = activity
        self.dheuof = dheuof
        self.llm = llm

    def _delegate_executor(self):
        def _run(args: dict) -> str:
            role_key = str(args.get("role") or "").strip()
            task = str(args.get("task") or "").strip()
            role = ROLES.get(role_key)
            if not role:
                return f"دورٌ غير معروف: {role_key}"
            self.activity.delegate(role_key, task)
            return run_role_agent(
                role=role, task=task, dheuof=self.dheuof, activity=self.activity,
                llm=self.llm, model=self.s.model, max_tokens=self.s.max_tokens,
                max_steps=self.s.max_agent_steps,
            )
        return {"delegate": _run}

    def handle(self, command: str) -> str:
        """يستقبل أمر المالك، يوزّعه على الطاقم، ويعيد الردّ النهائي."""
        self.activity.command(command)
        try:
            final = run_loop(
                llm=self.llm, model=self.s.model, max_tokens=self.s.max_tokens,
                system=_SYSTEM, tools=_delegate_schema(),
                execs=self._delegate_executor(), command=command,
                activity=self.activity, actor="orchestrator",
                max_steps=self.s.max_agent_steps,
            )
        except Exception as exc:
            self.activity.error("orchestrator", f"فشل تنفيذ الأمر: {exc}")
            raise
        self.activity.result(final)
        return final
