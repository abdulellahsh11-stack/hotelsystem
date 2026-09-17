#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
orchestrator.__main__ — تشغيلٌ محلّي: أعطِ الطاقمَ أمراً وشاهد كل حركة

    python -m orchestrator --subscription 11223344 "كم غرفة متاحة اليوم؟"
    python -m orchestrator --subscription 11223344 --watch     # بثّ سجلّ الحركة

المتغيّرات: ANTHROPIC_API_KEY · DHEUOF_API_KEY (مفتاح الاشتراك) ·
DHEUOF_BASE_URL · ORCH_MODEL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .activity import console_listener
from .config import Settings
from .team import Team


def _watch(settings: Settings) -> int:
    """يبثّ سجلّ حركة الطاقم من ملفّه (JSONL) حيّاً."""
    path = os.path.join(settings.activity_dir, f"team_{settings.subscription}.jsonl")
    print(f"👀 مراقبة حركة الطاقم {settings.subscription} — {path}")
    if not os.path.exists(path):
        print("لا سجلّ بعد — شغّل أمراً أولاً.")
        return 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                console_listener(json.loads(line))
            except Exception:
                pass
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="orchestrator", description="طاقم ضيوف لكل اشتراك")
    ap.add_argument("--subscription", "-s", required=True, help="رقم الاشتراك = رقم الطاقم")
    ap.add_argument("--watch", action="store_true", help="بثّ سجلّ الحركة بدل تنفيذ أمر")
    ap.add_argument("command", nargs="*", help="الأمر للطاقم")
    args = ap.parse_args(argv)

    settings = Settings.from_env(args.subscription)
    if args.watch:
        return _watch(settings)

    command = " ".join(args.command).strip()
    if not command:
        print("اكتب أمراً للطاقم، أو استعمل --watch.", file=sys.stderr)
        return 2
    try:
        settings.require()
    except ValueError as exc:
        print(f"إعدادٌ ناقص: {exc}", file=sys.stderr)
        return 2

    team = Team(settings)
    print(f"🏨 طاقم الاشتراك {team.number} — النموذج {settings.model}\n")
    final = team.command(command)
    print("\n" + "─" * 60)
    print("🏁 الرد النهائي:\n" + final)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
