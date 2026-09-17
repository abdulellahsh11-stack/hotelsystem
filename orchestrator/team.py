#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/team.py — تجميع الطاقم: اشتراكٌ واحد، ورقمُه رقمُ الطاقم

`Team` يربط الإعداد وسجلّ الحركة وعميل ضيوف والوكيل الرئيسي في وحدةٍ
واحدة لكل اشتراك. لاحقاً يُنقل كل `Team` إلى وكيل سحابةٍ صغيرٍ مستقل،
ورقمُه يبقى رقم الاشتراك — لا يتغيّر عند النقل.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .activity import ActivityLog, console_listener
from .config import Settings
from .dheuof import DheuofClient
from .orchestrator import Orchestrator


def _default_llm(settings: Settings):
    """عميل Anthropic الحقيقي — يُنشأ فقط عند التشغيل الفعلي."""
    import anthropic
    kwargs = {}
    if settings.anthropic_api_key:
        kwargs["api_key"] = settings.anthropic_api_key
    return anthropic.Anthropic(**kwargs)


class Team:
    """طاقمُ اشتراكٍ واحد جاهزٌ لاستقبال الأوامر."""

    def __init__(self, settings: Settings, *, llm: Any = None,
                 listener: Optional[Callable[[dict], None]] = console_listener,
                 http: Any = None):
        settings.require()
        self.settings = settings
        self.activity = ActivityLog(
            subscription=settings.subscription,
            directory=settings.activity_dir,
            listener=listener,
        )
        self.dheuof = DheuofClient(
            base_url=settings.dheuof_base_url, api_key=settings.dheuof_api_key,
            subscription=settings.subscription, activity=self.activity, http=http,
        )
        self.llm = llm if llm is not None else _default_llm(settings)
        self.orchestrator = Orchestrator(settings, self.activity, self.dheuof, self.llm)

    @property
    def number(self) -> str:
        """رقم الطاقم = رقم الاشتراك."""
        return self.settings.subscription

    def command(self, text: str) -> str:
        """يعطي الطاقمَ أمراً ويعيد الردّ النهائي (والحركة مسجَّلة كاملةً)."""
        return self.orchestrator.handle(text)

    def activity_log(self) -> list:
        """كل ما فعله الطاقم في هذه الجلسة — للمساءلة."""
        return list(self.activity.events)
