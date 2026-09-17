#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator/config.py — إعدادات الطاقم، من البيئة لا من الكود

الأسرار (مفتاح Anthropic، مفتاح API الخاصّ بالاشتراك) تُقرأ من متغيّرات
البيئة فلا تُكتب في الكود. رقم الاشتراك هو هوية الطاقم.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    """إعداد طاقمٍ واحد = اشتراكٍ واحد."""

    subscription: str                     # رقم الاشتراك = رقم الطاقم = client_id
    dheuof_api_key: str                   # مفتاح API الخاصّ بالاشتراك (dhk_…)
    dheuof_base_url: str = "http://localhost:5050"
    anthropic_api_key: str = ""           # يُقرأ من ANTHROPIC_API_KEY إن غاب
    model: str = "claude-opus-5"          # أي نموذج — يُضبط من ORCH_MODEL
    max_tokens: int = 4096
    activity_dir: str = "orchestrator/_activity"   # سجلّ الحركة (JSONL) لكل اشتراك
    max_agent_steps: int = 8              # حدّ حلقات الأداة لكل وكيل — لا لفٌّ لا نهائي
    approvals_required: bool = True       # العمليات الحسّاسة تحتاج موافقةً صريحة

    @classmethod
    def from_env(cls, subscription: str, **over) -> "Settings":
        """يبني الإعداد من البيئة، مع تجاوزاتٍ صريحة عند الحاجة."""
        key = over.pop("dheuof_api_key", None) or os.environ.get("DHEUOF_API_KEY", "")
        return cls(
            subscription=str(subscription),
            dheuof_api_key=key,
            dheuof_base_url=over.pop("dheuof_base_url", None)
            or os.environ.get("DHEUOF_BASE_URL", "http://localhost:5050"),
            anthropic_api_key=over.pop("anthropic_api_key", None)
            or os.environ.get("ANTHROPIC_API_KEY", ""),
            model=over.pop("model", None) or os.environ.get("ORCH_MODEL", "claude-opus-5"),
            **over,
        )

    def require(self) -> None:
        """يفشل بوضوحٍ لا صمت: طاقمٌ بلا رقمٍ أو بلا مفتاحٍ لا يعمل."""
        if not str(self.subscription).strip():
            raise ValueError("رقم الاشتراك مطلوب — هو هوية الطاقم")
        if not str(self.dheuof_api_key).strip():
            raise ValueError("مفتاح API الخاصّ بالاشتراك مطلوب (DHEUOF_API_KEY)")
