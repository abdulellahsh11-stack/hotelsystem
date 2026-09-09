#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/subscription.py — حالة الاشتراك والتنبيه قبل القفل (البند ٣).

التجربة ٣٠ يوماً؛ قبل القفل بـ٢٤ ساعة (اليوم ٢٩) يُرفع تنبيهٌ للمنشأة كي
تجدّد قبل أن تُقفل الوحدات. ورسالة الدفع (تحويل بنكي أو رابط ميسر) يكتبها
مالك المنشأة فتظهر عند التجديد — التحصيل الحقيقي عبر ميسر يحتاج مفاتيح
التاجر (تُضاف من البيئة) وليس من نطاق هذا المنطق.

منطقٌ خالص: `evaluate` تستقبل بيانات العميل ولحظةً (قابلة للحقن في
الاختبار) فتُحسب الحالة دون قاعدة بيانات.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

ALERT_WINDOW_HOURS = 24      # اليوم ٢٩: تنبيهٌ قبل القفل بـ٢٤ ساعة

# رسالة الدفع القابلة للتخصيص — الحقول المعروفة وحدها تُقبل.
_PAY_KEYS = ("method", "message", "bank_name", "iban",
             "account_name", "beneficiary", "moyasar_link")

DEFAULT_PAYMENT = {
    "method": "bank_transfer",
    "message": ("لتجديد الاشتراك حوِّل قيمة الباقة إلى الحساب البنكي أدناه ثم "
                "أرسل الإيصال، أو ادفع عبر رابط ميسر إن وُجد."),
    "bank_name": "",
    "iban": "",
    "account_name": "",
    "beneficiary": "",
    "moyasar_link": "",
}


def _parse_end(val) -> datetime | None:
    """يقبل datetime أو date أو نصّ ISO (تاريخٌ فقط يعني منتصف ليلته UTC)."""
    if not val:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evaluate(client: dict | None, now: datetime | None = None) -> dict:
    """حالة الاشتراك: متى ينتهي، كم بقي، هل يُنبَّه (٢٤ ساعة)، هل قُفل."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    c = client or {}
    out = {
        "status": c.get("status") or "trial",
        "sub_end": None,
        "days_remaining": None,
        "hours_remaining": None,
        "alert": False,
        "locked": False,
    }
    end = _parse_end(c.get("sub_end") or c.get("trial_end"))
    if not end:
        return out
    hours = (end - now).total_seconds() / 3600.0
    out["sub_end"] = end.date().isoformat()
    out["hours_remaining"] = round(hours, 1)
    out["days_remaining"] = max(0, math.floor(hours / 24)) if hours > 0 else 0
    out["locked"] = hours <= 0
    out["alert"] = 0 < hours <= ALERT_WINDOW_HOURS
    return out


# ── حالة الاشتراك: تفعيل · ترقية/هبوط · إلغاء · تجربة (خالصٌ) ────────

TRIAL_DAYS = 30

# رُتب الخطط — للترقية والهبوط والحمايات الخادمية.
PLAN_RANK = {"trial": 0, "starter": 1, "business": 2, "enterprise": 3}

# أدنى خطةٍ تُتيح كل وحدة. غير المذكور متاحٌ للجميع (starter فأعلى ضمنياً
# عبر القفل). الحماية خادميّة: القرار لا يُترك للواجهة.
MODULE_MIN_PLAN = {
    "channels": "business",       # ربط قنوات الحجز
    "insights": "business",       # التحليلات
    "accounting_export": "business",
    "api": "enterprise",          # وصول API
    "multi_property": "enterprise",
}


def _add_months(start: datetime, months: int) -> datetime:
    """يضيف أشهراً إلى تاريخٍ دون مكتبة خارجية (يضبط نهاية الشهر)."""
    m = start.month - 1 + int(months)
    year = start.year + m // 12
    month = m % 12 + 1
    # آخر يومٍ صالح في الشهر الهدف
    day = min(start.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                          else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return start.replace(year=year, month=month, day=day)


def start_trial(now: datetime | None = None) -> dict:
    """حقول بدء التجربة — ثلاثون يوماً."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    end = now + timedelta(days=TRIAL_DAYS)
    return {"status": "trial", "plan": "trial",
            "trial_end": end.date().isoformat(),
            "sub_end": end.date().isoformat()}


def activate(client: dict | None, plan: str, months: int = 1,
             now: datetime | None = None) -> dict:
    """يفعّل/يمدّد الاشتراك. يمدّد من الأبعد بين الآن ونهايةٍ قائمة (فلا
    تضيع أيامٌ متبقّية عند التجديد المبكّر). يعيد حقول الحساب للحفظ.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    plan = plan if plan in PLAN_RANK else "starter"
    months = max(1, int(months or 1))
    current_end = _parse_end((client or {}).get("sub_end"))
    base = current_end if (current_end and current_end > now) else now
    new_end = _add_months(base, months)
    return {"status": "active", "plan": plan,
            "sub_start": now.date().isoformat(),
            "sub_end": new_end.date().isoformat()}


def change_plan(client: dict | None, new_plan: str) -> dict:
    """ترقية أو هبوط — يبدّل الخطة ويُبقي نهاية المدّة كما هي.

    يعيد {"plan":.., "direction": "upgrade"|"downgrade"|"same"}؛ الفوترة
    التناسبية (proration) عند البوابة، وهذا يعكس القرار في حالتنا.
    """
    new_plan = new_plan if new_plan in PLAN_RANK else "starter"
    old = (client or {}).get("plan", "trial")
    old_rank, new_rank = PLAN_RANK.get(old, 0), PLAN_RANK[new_plan]
    direction = ("upgrade" if new_rank > old_rank
                 else "downgrade" if new_rank < old_rank else "same")
    return {"plan": new_plan, "direction": direction}


def cancel(client: dict | None, now: datetime | None = None) -> dict:
    """إلغاءٌ يعمل: يوقف التجديد ويُبقي الوصول حتى نهاية المدّة المدفوعة.

    لا يُقفل فوراً (العميل دفع للمدّة)، بل status=canceled وsub_end كما
    هو — فـ`is_accessible` يبقى صحيحاً حتى ينقضي.
    """
    return {"status": "canceled"}


def is_accessible(client: dict | None, now: datetime | None = None) -> bool:
    """هل للمنشأة وصولٌ الآن؟ نشطة/تجربة/ملغاة-بعد لم تنقضِ مدّتها."""
    ev = evaluate(client, now=now)
    status = (client or {}).get("status") or ev.get("status")
    if status == "suspended":
        return False
    return not ev["locked"]


def can_use(client: dict | None, module: str, now: datetime | None = None) -> bool:
    """حمايةٌ خادميّة: هل تُتيح خطة المنشأة هذه الوحدة، ووصولها ساري؟

    قرارٌ لا يُترك للواجهة: وحدةٌ تفوق الخطة، أو اشتراكٌ مقفل، تُمنع.
    """
    if not is_accessible(client, now=now):
        return False
    need = MODULE_MIN_PLAN.get(module)
    if not need:
        return True
    have = PLAN_RANK.get((client or {}).get("plan", "trial"), 0)
    return have >= PLAN_RANK[need]


def sanitize_payment(data) -> dict:
    """يُبقي حقول رسالة الدفع المعروفة فقط، نصوصاً مُشذّبة."""
    out: dict[str, str] = {}
    if isinstance(data, dict):
        for k in _PAY_KEYS:
            v = data.get(k)
            if v is not None:
                out[k] = str(v).strip()
    return out


def payment_instructions(client: dict | None) -> dict:
    """تعليمات الدفع لهذه المنشأة — المخصَّص فوق الافتراضي."""
    merged = dict(DEFAULT_PAYMENT)
    stored = ((client or {}).get("settings") or {}).get("subscription_payment")
    if isinstance(stored, dict):
        merged.update(sanitize_payment(stored))
    return merged
