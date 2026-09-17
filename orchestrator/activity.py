#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/activity.py — «خبرٌ بكل حركة»: سجلّ حركة الطاقم وبثُّه الحيّ

كل ما يفعله الطاقم يمرّ من هنا: أمرٌ من المالك، تفويضٌ لوكيل، نداء أداة،
نتيجة، ردٌّ نهائي، أو خطأ. يُكتب سطراً JSONL دائماً (سجلٌّ لكل اشتراك)،
ويُبثّ حيّاً عبر مُستمعٍ اختياري (الطرفية الآن، وقناةٌ خارجية لاحقاً).

المبدأ: لا حركة بلا أثرٍ يراه المالك. السجلّ مصدر الحقيقة للمساءلة.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

# أنواع الأحداث — مفرداتٌ مضبوطة لا نصٌّ حر، فتُقرأ وتُصفّى بثبات.
COMMAND = "command"          # أمرٌ من المالك دخل الطاقم
PLAN = "plan"                # خطة الوكيل الرئيسي
DELEGATE = "delegate"        # تفويضٌ لوكيل دور
AGENT_START = "agent_start"  # بدء وكيل دور
TOOL_CALL = "tool_call"      # نداء أداة (أيّ حركةٍ فعلية)
TOOL_RESULT = "tool_result"  # نتيجة الأداة
APPROVAL = "approval"        # طلب/منح موافقةٍ على عمليةٍ حسّاسة
AGENT_REPLY = "agent_reply"  # ردّ وكيل الدور
RESULT = "result"            # الردّ النهائي للمالك
ERROR = "error"              # خطأ


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ActivityLog:
    """سجلّ حركةٍ لطاقمِ اشتراكٍ واحد: يكتب JSONL ويبثّ حيّاً."""

    subscription: str
    directory: str = "orchestrator/_activity"
    listener: Optional[Callable[[dict], None]] = None   # بثٌّ حيّ (طرفية/قناة)
    events: list = field(default_factory=list)
    _seq: int = 0

    @property
    def path(self) -> str:
        return os.path.join(self.directory, f"team_{self.subscription}.jsonl")

    def record(self, kind: str, actor: str, message: str, **data) -> dict:
        """يسجّل حدثاً واحداً: يُخزَّن ويُبثّ. لا يفشل الطاقم لو تعذّر الكتابة."""
        self._seq += 1
        ev = {
            "seq": self._seq,
            "ts": _now(),
            "subscription": self.subscription,
            "kind": kind,
            "actor": actor,           # من نفّذ: orchestrator أو اسم وكيل الدور
            "message": message,
            "data": data or {},
        }
        self.events.append(ev)
        try:
            os.makedirs(self.directory, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        except Exception:
            pass  # السجلّ في الذاكرة يبقى؛ فشل القرص لا يوقف الطاقم
        if self.listener:
            try:
                self.listener(ev)
            except Exception:
                pass
        return ev

    # اختصاراتٌ مقروءة لكل نوع حركة
    def command(self, text: str) -> dict:
        return self.record(COMMAND, "owner", text)

    def plan(self, text: str, **d) -> dict:
        return self.record(PLAN, "orchestrator", text, **d)

    def delegate(self, role: str, task: str) -> dict:
        return self.record(DELEGATE, "orchestrator", f"تفويض إلى {role}", role=role, task=task)

    def agent_start(self, role: str) -> dict:
        return self.record(AGENT_START, role, f"بدأ وكيل {role}")

    def tool_call(self, actor: str, tool: str, args: dict) -> dict:
        return self.record(TOOL_CALL, actor, f"نداء أداة: {tool}", tool=tool, args=args)

    def tool_result(self, actor: str, tool: str, ok: bool, summary: str) -> dict:
        return self.record(TOOL_RESULT, actor, f"نتيجة {tool}", tool=tool, ok=ok, summary=summary)

    def approval(self, actor: str, tool: str, granted: bool, args: dict) -> dict:
        state = "مُنحت" if granted else "طُلبت"
        return self.record(APPROVAL, actor, f"موافقة {state}: {tool}", tool=tool,
                           granted=granted, args=args)

    def agent_reply(self, role: str, text: str) -> dict:
        return self.record(AGENT_REPLY, role, text)

    def result(self, text: str) -> dict:
        return self.record(RESULT, "orchestrator", text)

    def error(self, actor: str, text: str) -> dict:
        return self.record(ERROR, actor, text)


def console_listener(ev: dict) -> None:
    """بثٌّ حيٌّ للطرفية — سطرٌ لكل حركة، ملوّنٌ بالرمز."""
    icon = {
        COMMAND: "📥", PLAN: "🧭", DELEGATE: "➡️", AGENT_START: "🟢",
        TOOL_CALL: "🔧", TOOL_RESULT: "✅", APPROVAL: "🔐",
        AGENT_REPLY: "💬", RESULT: "🏁", ERROR: "⛔",
    }.get(ev["kind"], "•")
    t = ev["ts"].split("T")[-1][:8]
    line = f"{icon} [{t}] {ev['actor']}: {ev['message']}"
    extra = ev.get("data") or {}
    if ev["kind"] == TOOL_CALL and extra.get("args"):
        line += f"  · {json.dumps(extra['args'], ensure_ascii=False)}"
    print(line, flush=True)
