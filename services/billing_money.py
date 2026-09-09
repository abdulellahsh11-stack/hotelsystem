#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/billing_money.py — حساب المال قبل الانطلاق الحيّ (ثلاثة بنود).

قبل قلب الفوترة إلى الوضع الحيّ نحتاج ثلاثة أشياء لا تحتمل التقريب
الخاطئ ولا العملة المغلوطة ولا الرسالة المبهمة:

- **ضريبة القيمة المضافة** — `add_vat` تضيفها على مبلغٍ صافٍ، و`extract_vat`
  تستخرجها من إجماليٍّ يحويها أصلاً (فاتورةٌ شاملة). كلاهما يقرّب لخانتين،
  ويرفض السالب وغير الرقمي — فلا فاتورةٌ بضريبةٍ عكسية ولا NaN يتسرّب.
- **تعدّد العملات** — تحويلٌ بين الوحدة الكبرى والصغرى بجدول أسٍّ لكل عملة،
  متوافقٍ مع `_to_major`/`_CURRENCY_EXP` في services/moyasar.py: ميسر يرسل
  ويستقبل بالوحدة الصغرى، وخلطُ الأسّ يعني رسماً بمئةِ ضعفٍ أو بجزءٍ منه.
- **البطاقات المنتهية والرفض** — تصنيفٌ ثابتٌ لرموز الرفض إلى سببٍ داخليٍّ
  موحّد، كي تُعرض للمستخدم علّةٌ قابلةٌ للتصرّف بدل «فشل الدفع» المبهم.

المنطق **خالصٌ** (بلا قاعدة بيانات) كي يُختبَر بالكسر؛ ليس هنا لمسٌ للقاعدة،
فإن أُضيف لاحقاً فيُعزَل في دوالٍّ تحرس `use_postgres` كما في services/payments.
"""
from __future__ import annotations

# أسّ الوحدة الصغرى لكل عملة (كم خانة كسرية). يُبقى متوافقاً مع
# services/moyasar._CURRENCY_EXP — مصدرٌ واحدٌ للحقيقة لو دُمجا لاحقاً.
_CURRENCY_EXP = {
    "SAR": 2, "USD": 2, "EUR": 2, "AED": 2, "EGP": 2, "QAR": 2,
    "JPY": 0, "KWD": 3, "BHD": 3, "JOD": 3, "OMR": 3,
}

_DEFAULT_CURRENCY = "SAR"
_DEFAULT_EXP = 2


# ── تعدّد العملات ────────────────────────────────────────────────────

def normalize_currency(code) -> str:
    """رمز عملةٍ معروفٍ بأحرفٍ كبيرة دائماً — غير المعروف يعود إلى الريال."""
    c = str(code or "").strip().upper()
    return c if c in _CURRENCY_EXP else _DEFAULT_CURRENCY


def _exp(currency) -> int:
    """أسّ العملة (عدد الخانات الكسرية) — غير المعروف خانتان كالريال."""
    return _CURRENCY_EXP.get(str(currency or "").strip().upper(), _DEFAULT_EXP)


def to_minor(amount, currency) -> int:
    """وحدةٌ كبرى → وحدةٌ صغرى (ريالٌ → هللة). يعيد عدداً صحيحاً.

    مبلغٌ غير رقميٍّ أو سالبٌ يرفع ValueError — لا نرسل للبوّابة رسماً مشوّهاً.
    """
    try:
        major = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"مبلغٌ غير صالح: {amount!r}")
    if major < 0 or major != major:              # يرفض السالب وNaN
        raise ValueError(f"مبلغٌ غير صالح: {amount!r}")
    exp = _exp(currency)
    return int(round(major * (10 ** exp)))


def from_minor(minor, currency) -> float:
    """وحدةٌ صغرى → وحدةٌ كبرى (هللةٌ → ريال). يقرّب لأسّ العملة.

    مبلغٌ غير رقميٍّ أو سالبٌ يرفع ValueError.
    """
    try:
        m = int(minor)
    except (TypeError, ValueError):
        raise ValueError(f"مبلغٌ غير صالح: {minor!r}")
    if m < 0:
        raise ValueError(f"مبلغٌ غير صالح: {minor!r}")
    exp = _exp(currency)
    return round(m / (10 ** exp), exp)


# ── ضريبة القيمة المضافة ─────────────────────────────────────────────

def _validate_rate(rate) -> float:
    try:
        r = float(rate)
    except (TypeError, ValueError):
        raise ValueError(f"نسبةٌ غير صالحة: {rate!r}")
    if r < 0 or r != r:
        raise ValueError(f"نسبةٌ غير صالحة: {rate!r}")
    return r


def _validate_amount(amount, label: str) -> float:
    try:
        a = float(amount)
    except (TypeError, ValueError):
        raise ValueError(f"{label} غير صالح: {amount!r}")
    if a < 0 or a != a:
        raise ValueError(f"{label} غير صالح: {amount!r}")
    return a


def add_vat(base_amount, rate: float = 0.15) -> dict:
    """يضيف الضريبة على مبلغٍ صافٍ. يعيد {base, vat, total} مقرَّبةً لخانتين.

    الأساس هو المبلغ قبل الضريبة؛ `total = base + vat`. يرفض السالب/غير الرقمي.
    """
    base = _validate_amount(base_amount, "الأساس")
    r = _validate_rate(rate)
    base = round(base, 2)
    vat = round(base * r, 2)
    total = round(base + vat, 2)
    return {"base": base, "vat": vat, "total": total}


def extract_vat(total, rate: float = 0.15) -> dict:
    """يستخرج الضريبة من إجماليٍّ يحويها (فاتورةٌ شاملة). يعيد {base, vat, total}.

    عكس add_vat: `base = total / (1 + rate)`، و`vat = total - base`. مقرَّبٌ
    لخانتين، رافضٌ للسالب/غير الرقمي. round-trip مع add_vat يعود لنفس الإجمالي.
    """
    tot = _validate_amount(total, "الإجمالي")
    r = _validate_rate(rate)
    tot = round(tot, 2)
    base = round(tot / (1 + r), 2)
    vat = round(tot - base, 2)
    return {"base": base, "vat": vat, "total": tot}


# ── البطاقات المنتهية والرفض ─────────────────────────────────────────

# رموز/حالات ميسر (وما شابهها من البوّابات) → سببٌ داخليٌّ موحّد.
# المفتاح مطبَّعٌ (أحرفٌ صغيرة، شرطاتٌ سفلية بدل المسافات) قبل البحث.
_FAILURE_REASONS = {
    "expired": "expired_card",
    "expired_card": "expired_card",
    "card_expired": "expired_card",
    "insufficient_funds": "insufficient_funds",
    "insufficient": "insufficient_funds",
    "declined": "declined",
    "card_declined": "declined",
    "do_not_honor": "declined",
    "do_not_honour": "declined",
    "invalid_card": "invalid_card",
    "invalid_card_number": "invalid_card",
    "incorrect_number": "invalid_card",
    "invalid_cvc": "invalid_cvc",
    "incorrect_cvc": "invalid_cvc",
    "invalid_expiry": "invalid_expiry",
    "incorrect_expiry": "invalid_expiry",
    "lost_card": "card_blocked",
    "stolen_card": "card_blocked",
    "restricted_card": "card_blocked",
    "authentication_failed": "authentication_failed",
    "3ds_failed": "authentication_failed",
    "processing_error": "processing_error",
    "timeout": "processing_error",
}

_EXPIRED_REASON = "expired_card"


def _normalize_token(value) -> str:
    """يطبّع رمزاً نصّياً: أحرفٌ صغيرة، مسافاتٌ وشرطاتٌ → شرطةٌ سفلية."""
    s = str(value or "").strip().lower()
    for ch in (" ", "-", ".", "/"):
        s = s.replace(ch, "_")
    while "__" in s:
        s = s.replace("__", "_")
    return s.strip("_")


def card_failure_reason(status, source) -> str:
    """يصنّف فشل بطاقةٍ إلى سببٍ داخليٍّ ثابت.

    `status` حالة الدفعة (مثل failed/declined)، و`source` تفصيلها من ميسر
    (رمز/رسالة الرفض). يُفحص التفصيل أولاً لأنه أدقّ، ثم الحالة. غير المعروف
    يعود إلى `unknown` — سببٌ ثابتٌ لا رسالةٌ نيّئة تُعرض للمستخدم.
    """
    for candidate in (source, status):
        tok = _normalize_token(candidate)
        if not tok:
            continue
        if tok in _FAILURE_REASONS:
            return _FAILURE_REASONS[tok]
        # مطابقةٌ جزئية: رسالةٌ مثل "your card is expired" أو "card was declined".
        for key, reason in _FAILURE_REASONS.items():
            if key in tok:
                return reason
    return "unknown"


def is_expired_card(status, message) -> bool:
    """هل يعود الفشل إلى بطاقةٍ منتهية؟ يفحص الحالة والرسالة معاً.

    يُستعمل لتوجيه المستخدم إلى تحديث البطاقة تحديداً بدل «حاول مجدّداً».
    """
    return card_failure_reason(status, message) == _EXPIRED_REASON
