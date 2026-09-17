#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/access.py — مسارات PMS الأربعة، كلٌّ بحارسه

نظام PMS واضح: من يدخل، ومن أين، وماذا يبلغ. أربعة مساراتٍ داخلية
لا تتداخل.

    ١ مالك المنصة   /admin      كل شيء عبر كل المنشآت · جلسة admin_token
    ٢ مالك المنشأة  /login      منشأته كاملةً · يعيّن المدير والموظفين
    ٣ مدير المنشأة  /staff      صلاحياته من المالك · يعيّن الموظفين
    ٤ الموظفون      /staff      صلاحياتهم من المدير · كلٌّ بحدّ وظيفته

الثلاثة الأخيرة (٢ · ٣ · ٤) يحجزون للضيوف داخل المنشأة.

**الزائر ليس مساراً من مسارات PMS.** هو جهة تطبيق الحجز وحدها —
يحجز لنفسه من بوابةٍ عامّة، ولا يدخل أي تطبيق تشغيل. لذلك حارسُه
`require_visitor` يعيش في `services/visitor_session.py` مع جلسته
المنفصلة (كوكي `visitor_token` وجدول `visitor_sessions`)، لا هنا:
إبقاؤه بين حرّاس المنشأة يوحي بأنه مرتبةٌ داخلية، وهو ليس كذلك. ولو
حجز باسم غيره لصار بابَ إدخالِ هوياتٍ لا يملكها — تسريبٌ بالعكس —
فيمنعه `require_can_book_for_guests` أدناه لو نُودي.

لماذا ملفٌ منفصل: كان `require_client` وحده يحرس المالك والمدير
والموظف معاً، فلا يُقرأ من المسار من يحقّ له. فرقُ المرتبة يُقرأ الآن
من اسم الحارس نفسه.

**كل حارسٍ هنا يقرأ الجلسة من الخادم.** لا من مسار، ولا من جسم طلب،
ولا من رأسٍ يرسله المتصفّح.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

# ── المراتب ─────────────────────────────────────────────────────
OWNER = "owner"          # مالك المنشأة — حساب الاشتراك
MANAGER = "gm"           # مدير عام — يعيّنه المالك وحده
STAFF_ROLES = frozenset({"manager", "receptionist", "housekeeping",
                         "accountant", "pos_cashier"})

#: من يحقّ له الحجز لضيفٍ آخر. الزائر ليس منهم.
CAN_BOOK_FOR_GUESTS = frozenset({OWNER, MANAGER}) | STAFF_ROLES


def _session(request: Request) -> dict:
    """جلسة المنشأة من الخادم، أو ٤٠١."""
    from app_core import get_client_session

    session = get_client_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="غير مصرح — سجّل الدخول")
    if not str(session.get("client_id") or "").strip():
        raise HTTPException(status_code=401, detail="جلسة غير صالحة — رقم المنشأة مفقود")
    return session


def actor_label(session: dict) -> str:
    """
    اسم من نفّذ الإجراء، لسجلّ المساءلة: من أدخل البيانات أو غيّر حالة
    الغرفة أو سجّل النزيل.

    الاسم الكامل أوّلاً، ثم اسم المستخدم، وإلا تسمية الدور بالعربية —
    فلا يبقى سطرٌ في السجلّ بلا فاعلٍ معروف. مالك المنشأة قد لا يحمل
    `username`، فيُنسَب بصفته.
    """
    s = session or {}
    name = str(s.get("full_name") or "").strip() or str(s.get("username") or "").strip()
    if name:
        return name[:100]
    role = role_of(s)
    try:
        from services.staff_roles import ROLES
        return str(ROLES.get(role, {}).get("label") or role)[:100]
    except Exception:
        return role[:100]


def role_of(session: dict) -> str:
    """
    دور الجلسة، بافتراض `owner` عند غيابه.

    الغياب يعني صفّاً كُتب قبل إضافة أعمدة الهوية، وتلك جلسات مالكٍ
    حصراً — لم تكن جلسات موظفين آنذاك.
    """
    return str((session or {}).get("role") or OWNER)


# ── ١ · مالك المنصة ─────────────────────────────────────────────
def require_platform_owner(request: Request) -> dict:
    """جلسة `admin_token` المنفصلة. لا يملك حساباً في أي منشأة."""
    from app_core import require_admin

    return require_admin(request)


# ── ٢ · مالك المنشأة ────────────────────────────────────────────
def require_facility_owner(request: Request) -> dict:
    """
    المالك وحده — لا المدير العام.

    لِما يُنشئ نِدّاً أو يمسّ الاشتراك: تعيين مديرٍ عام، وإنهاء
    الاشتراك، وما لا يُستردّ.
    """
    session = _session(request)
    if role_of(session) != OWNER:
        raise HTTPException(
            status_code=403,
            detail="هذا الإجراء لمالك المنشأة وحده",
        )
    return session


# ── ٣ · المدير فما فوق ──────────────────────────────────────────
def require_manager(request: Request) -> dict:
    """المالك أو مديره العام — من يعيّن الموظفين ويضبط الإعدادات."""
    session = _session(request)
    if role_of(session) not in (OWNER, MANAGER):
        raise HTTPException(
            status_code=403,
            detail="هذا الإجراء لمالك المنشأة أو مديرها العام",
        )
    return session


# ── ٤ · أي منتسبٍ للمنشأة ───────────────────────────────────────
def require_staff(request: Request) -> dict:
    """
    أي حسابٍ داخل المنشأة: مالكاً أو مديراً أو موظفاً.

    يمنع الزائر: جلسته من نوعٍ آخر ولا تحمل دوراً معروفاً هنا، فلا
    تبلغ شاشات التشغيل ولو صحّت الكوكي.
    """
    session = _session(request)
    role = role_of(session)
    if role not in CAN_BOOK_FOR_GUESTS:
        raise HTTPException(
            status_code=403,
            detail="هذه الشاشة لموظفي المنشأة — الزوّار يحجزون من بوابة الحجز",
        )
    return session


# ── الحجز للضيوف ────────────────────────────────────────────────
def require_can_book_for_guests(request: Request) -> dict:
    """
    من يحجز باسم ضيفٍ ويُدخل هويته.

    الزائر يحجز لنفسه من بوابته ولا يمرّ من هنا إطلاقاً — بوابته لا
    تنادي هذا المسار أصلاً، وهذا الحارس يمنعه لو نُودي.
    """
    return require_staff(request)
