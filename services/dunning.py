#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/dunning.py — إعادة محاولة رسائل الديون (بند: منطق إعادة المحاولة).

حين تفشل دفعةٌ متعلّقة بدَينٍ (تجديد اشتراكٍ أو فاتورةٍ مستحقّة) لا نكتفي
برسالةٍ واحدة: نعيد المحاولة بفواصل متباعدة (تراجعٌ أسّي مُقيَّد) وبنبرةٍ
تتصاعد مع المحاولة، ثم نتوقّف بعد حدٍّ أقصى.

كل ما هنا **خالصٌ وقابلٌ للحقن**: `next_attempt` تُعطي متى المحاولة
التالية، `should_retry` تقول هل نُكمل، و`dunning_message` تبني الرسالة —
بلا قاعدةٍ ولا شبكة، فتُختبَر بالكسر (جدول الفواصل، توقّف الحدّ، تصاعد
النبرة).
"""
from __future__ import annotations

import html

BASE_HOURS = 24        # فاصل المحاولة الأولى
MAX_HOURS = 168        # سقف الفاصل (أسبوع)
MAX_ATTEMPTS = 4       # عدد المحاولات قبل التوقّف


def next_attempt(attempt_no: int, base_hours: int = BASE_HOURS,
                 max_hours: int = MAX_HOURS) -> int:
    """ساعات الانتظار قبل المحاولة رقم `attempt_no` — تراجعٌ أسّي مُقيَّد.

    الأولى بعد `base_hours`، ثم تتضاعف: ٢٤ · ٤٨ · ٩٦ · ١٩٢ …، مقصوصةً
    عند `max_hours` (١٦٨). رقمٌ ≤ ١ يُعامَل معاملة المحاولة الأولى.
    """
    n = max(1, int(attempt_no or 1))
    hours = base_hours * (2 ** (n - 1))
    return min(hours, max_hours)


def should_retry(attempt_no: int, max_attempts: int = MAX_ATTEMPTS) -> bool:
    """هل نُعيد المحاولة؟ نتوقّف بعد بلوغ `max_attempts`."""
    return int(attempt_no or 0) < int(max_attempts)


# نبرةٌ متصاعدة لكل محاولة — العربية والإنجليزية.
_TONE = {
    "ar": [
        {"subject": "تذكير: لم تكتمل عملية الدفع",
         "opening": "نودّ تذكيرك بأنّ دفعة اشتراكك لم تكتمل. يُرجى إكمالها في أقرب وقت."},
        {"subject": "تنبيه: دفعتك ما زالت معلّقة",
         "opening": "ما زالت دفعتك معلّقة. نرجو تسويتها لتجنّب انقطاع الخدمة."},
        {"subject": "هام: مستحقّاتٌ متأخّرة على حسابك",
         "opening": "توجد مستحقّاتٌ متأخّرة على حسابك. يُرجى السداد فوراً لتفادي إيقاف الخدمة."},
        {"subject": "إشعار أخير قبل إيقاف الخدمة",
         "opening": "هذا إشعارٌ أخير: سيتمّ إيقاف الخدمة ما لم تُسدَّد المستحقّات المتأخّرة الآن."},
    ],
    "en": [
        {"subject": "Reminder: your payment didn't go through",
         "opening": "A friendly reminder that your subscription payment was not completed. Please complete it soon."},
        {"subject": "Notice: your payment is still pending",
         "opening": "Your payment is still pending. Please settle it to avoid any service interruption."},
        {"subject": "Important: overdue balance on your account",
         "opening": "There is an overdue balance on your account. Please pay now to avoid service suspension."},
        {"subject": "Final notice before service suspension",
         "opening": "This is a final notice: service will be suspended unless the overdue balance is paid now."},
    ],
}

_CLOSING = {
    "ar": "شكراً لتعاونك — فريق منصة ضيوف.",
    "en": "Thank you — the Dheuof team.",
}


def _lang_key(lang) -> str:
    return "en" if str(lang or "ar").strip().lower() == "en" else "ar"


def _tone(lang: str, attempt_no: int) -> dict:
    """يختار نبرة المحاولة — يُقصَر ضمن الجدول (الأخيرة أشدّ)."""
    tones = _TONE[_lang_key(lang)]
    idx = max(1, int(attempt_no or 1)) - 1
    return tones[min(idx, len(tones) - 1)]


def _client_name(client: dict, lang: str) -> str:
    c = client or {}
    name = (c.get("name") or c.get("facility") or c.get("hotel_name") or "").strip()
    if name:
        return name
    return "عميلنا العزيز" if _lang_key(lang) == "ar" else "Dear customer"


def dunning_message(client: dict, attempt_no: int, lang: str = "ar") -> dict:
    """يبني رسالة تذكيرٍ بالدَّين بنبرةٍ تناسب رقم المحاولة.

    يعيد {"subject": .., "body_text": ..}. الرسالة نصّية (يبنيها المُرسِل
    في HTML عند الحاجة، مُهرِّباً القيم). اسم العميل يُهرَّب هنا وقائياً
    لئلا يتسرّب وسمٌ إلى أيّ عرضٍ لاحق.
    """
    lk = _lang_key(lang)
    tone = _tone(lang, attempt_no)
    name = html.escape(_client_name(client, lang))

    if lk == "ar":
        greeting = f"مرحباً {name}،"
    else:
        greeting = f"Hello {name},"

    body_text = "\n".join([greeting, "", tone["opening"], "", _CLOSING[lk]])
    return {"subject": tone["subject"], "body_text": body_text}
