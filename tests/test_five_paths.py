#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_five_paths.py — مسارات PMS الأربعة لا تتداخل، والزائر خارجها

    ١ مالك المنصة   كل شيء عبر كل المنشآت
    ٢ مالك المنشأة  منشأته كاملةً · يعيّن المدير
    ٣ مدير المنشأة  يعيّن الموظفين لا نظراءه
    ٤ الموظفون      كلٌّ بحدّ وظيفته
    — الزائر        جهة تطبيق الحجز وحدها · حجزٌ لأنفسهم · لا يدخل تطبيقاً

الزائر ليس مساراً من مسارات PMS: حارسُه يعيش في طبقة الحجز
(`services/visitor_session.py`) لا بين حرّاس المنشأة في `db/access.py`.
وهو الأخطر: بوابةٌ عامّة على الإنترنت، وأي ثغرةٍ فيها تُفتح على منشآت
كل العملاء. لذلك أكثر الاختبارات هنا تبدأ بمحاولةٍ **يجب أن تُرفض**،
لا بمحاولةٍ تنجح.
"""
import ast
from pathlib import Path

import pytest

from db.access import (
    CAN_BOOK_FOR_GUESTS,
    MANAGER,
    OWNER,
    STAFF_ROLES,
    role_of,
)

ROOT = Path(__file__).resolve().parent.parent
VISITORS = ROOT / "routes/visitors.py"
ACCESS = ROOT / "db/access.py"
VISITOR_SESSION = ROOT / "services/visitor_session.py"


# ── المراتب ─────────────────────────────────────────────────────
def test_visitor_is_not_among_those_who_book_for_guests():
    """
    جوهر المسار الخامس. لو دخل الزائر هذه المجموعة لصار يحجز باسم
    غيره، فتصير البوابة باب إدخال هوياتٍ لا يملكها المُدخِل.
    """
    assert "visitor" not in CAN_BOOK_FOR_GUESTS
    assert CAN_BOOK_FOR_GUESTS == {OWNER, MANAGER} | STAFF_ROLES


def test_role_of_defaults_to_owner():
    """جلسة المالك قد تصل بلا `role` — وتلك جلسات مالكٍ حصراً."""
    assert role_of({}) == OWNER
    assert role_of(None) == OWNER
    assert role_of({"role": "receptionist"}) == "receptionist"


def test_visitor_session_carries_no_role():
    """
    جلسة الزائر تحمل `kind` لا `role`.

    لو حملت `role` لصارت تُقرأ من `role_of` — وغيابُ القيمة يُفترض
    `owner`، فيصير زائرٌ مالكاً بحقلٍ منسيّ.
    """
    src = (ROOT / "services/visitor_session.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            keys = [k.value for k in node.keys if isinstance(k, ast.Constant)]
            if "visitor_id" in keys:
                assert "role" not in keys, "جلسة الزائر تحمل `role` — تُقرأ كموظف"
                assert "kind" in keys


# ── حرّاس منفصلون بأسماءٍ صريحة ─────────────────────────────────
@pytest.mark.parametrize("guard", [
    "require_platform_owner", "require_facility_owner",
    "require_manager", "require_staff",
])
def test_each_pms_path_has_its_own_guard(guard):
    """
    أربعة حرّاس PMS بأسماءٍ تُقرأ. حارسٌ واحد لكل المراتب — كما كان
    `require_client` — يُخفي من يحقّ له من قارئ المسار.
    """
    assert "def %s(" % guard in ACCESS.read_text(encoding="utf-8")


def test_visitor_guard_lives_in_the_booking_layer_not_among_pms_guards():
    """
    الزائر جهة تطبيق الحجز، لا مساراً من مسارات PMS. لذلك حارسُه في
    طبقة الحجز لا بين حرّاس المنشأة: إبقاؤه في `db/access.py` يوحي
    بأنه مرتبةٌ داخلية، وهذا اللبس هو ما يُطلب إزالته.
    """
    access_src = ACCESS.read_text(encoding="utf-8")
    session_src = VISITOR_SESSION.read_text(encoding="utf-8")
    assert "def require_visitor(" not in access_src, \
        "حارس الزائر ما زال بين حرّاس PMS في db/access.py"
    assert "def require_visitor(" in session_src, \
        "حارس الزائر مفقودٌ من طبقة الحجز services/visitor_session.py"


# ── بوابة الزوّار ───────────────────────────────────────────────
def test_every_visitor_route_is_guarded():
    """لا مسارٌ في البوابة بلا حارس — عدا التسجيل والدخول والخروج."""
    src = VISITORS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    OPEN = {"visitor_register", "visitor_login", "visitor_logout"}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in
                   ("get", "post", "delete", "patch", "put")
                   for d in node.decorator_list):
            continue
        if node.name in OPEN:
            continue
        body = ast.get_source_segment(src, node) or ""
        assert "require_visitor(request)" in body, \
            "%s بلا حارس زائر" % node.name


def test_visitor_queries_are_scoped_to_the_visitor():
    """
    كل استعلامٍ على `visitor_bookings` يُصفّى بـ`visitor_id`.

    بدونه يرى زائرٌ طلبات كل زوّار المنشأة — وفيها تواريخ وصولهم.
    """
    src = VISITORS.read_text(encoding="utf-8")
    for stmt in src.split("visitor_bookings")[1:]:
        window = stmt[:400]
        if "SELECT" in window or "DELETE" in window or "WHERE" in window:
            assert "visitor_id" in window, "استعلام بلا تصفية بـ visitor_id"


def test_visitor_never_supplies_another_persons_identity():
    """
    البوابة لا تقبل اسم ضيفٍ ولا رقم هوية.

    الزائر صاحب الجلسة هو صاحب الطلب. أي حقلٍ يقبل اسم غيره يجعل
    البوابة قناة إدخال بياناتٍ شخصية بلا تحقّق.
    """
    src = VISITORS.read_text(encoding="utf-8")
    body = src.split("async def visitor_request_booking")[1].split("\nasync def")[0]
    for banned in ("id_number", "guest_name", "full_name", "id_type"):
        assert 'data.get("%s"' % banned not in body, \
            "طلب حجز الزائر يقبل %s — هوية شخصٍ آخر" % banned


def test_client_id_comes_from_session_after_login():
    """
    `client_id` من جسم الطلب في التسجيل والدخول وحدهما.

    قراءته من الطلب بعد الدخول تعني أن زائراً يبدّل رقماً فيرى منشأةً
    أخرى — وهو كسرُ العزل بين المستأجرين مباشرةً.
    """
    src = VISITORS.read_text(encoding="utf-8")
    tree = ast.parse(src)
    allowed = {"visitor_register", "visitor_login"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name not in allowed:
            body = ast.get_source_segment(src, node) or ""
            assert 'data.get("client_id")' not in body, \
                "%s يقرأ client_id من الطلب" % node.name


def test_visitor_room_listing_hides_room_numbers():
    """
    الزائر يرى الأنواع والأسعار لا أرقام الغرف.

    أرقام الغرف وحالاتها تكشف إشغال المنشأة — ومن في أي غرفة.
    """
    src = VISITORS.read_text(encoding="utf-8")
    body = src.split("async def visitor_rooms")[1].split("\n# ──")[0]
    assert "room_number" not in body
    assert "GROUP BY" in body


def test_visitor_cancel_checks_status_not_only_owner():
    """
    الإلغاء مشروطٌ بـ`pending` **وبـ`visitor_id`**.

    بلا الأول يُلغي الزائر حجزاً أكّدته المنشأة وحضّرت له غرفة؛ وبلا
    الثاني يُلغي طلب غيره.
    """
    src = VISITORS.read_text(encoding="utf-8")
    body = src.split("async def visitor_cancel")[1]
    assert "status='pending'" in body
    assert "visitor_id=%s" in body


# ── فصل الكوكي والجدول ──────────────────────────────────────────
def test_visitor_cookie_and_table_are_separate():
    """
    كوكيٌّ وجدولٌ مستقلّان. المشاركة تعني أن خطأً واحداً في التحقق
    يمنح زائراً صلاحيات موظف.
    """
    # يُفحص الكود لا التعليقات: الوثائق تذكر جدول المنشأة عمداً لتشرح
    # الفصل، وفحصُ النصّ الخام يجعل كل شرحٍ جيدٍ يُسقط الاختبار.
    src = (ROOT / "services/visitor_session.py").read_text(encoding="utf-8")
    code = "\n".join(
        line.split("#")[0] for line in src.splitlines()
        if not line.strip().startswith("#")
    )
    tree = ast.parse(src)
    docs = {ast.get_docstring(n) or "" for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef))}
    for doc in docs:
        code = code.replace(doc, "")

    assert 'COOKIE_NAME = "visitor_token"' in src
    assert "client_token" not in code, "الكود يلمس كوكي المنشأة"
    assert "visitor_sessions" in code
    assert "client_sessions" not in code, "الكود يلمس جدول جلسات المنشأة"


def test_visitor_cookie_follows_the_app_wide_policy():
    """
    قاعدةٌ واحدة لـ`secure`، لا ثانية.

    اخترعتُ هنا افتراضاً مختلفاً فرفض المتصفّح الكوكي خارج HTTPS ولم
    تثبت جلسة زائرٍ واحدة — والتسجيل يعود ٢٠٠ فيبدو الباب سليماً.
    """
    src = (ROOT / "services/visitor_session.py").read_text(encoding="utf-8")
    assert "from app_core import _COOKIE_SECURE" in src
    assert 'os.getenv("COOKIE_SECURE"' not in src


def test_visitors_table_stores_no_national_id():
    """
    لا رقم هوية في جدول الزوّار.

    الهوية تُؤخذ عند الوصول من موظفٍ مخوَّل بشاشةٍ تُشفّرها. جمعُها من
    نموذجٍ عامّ يعني تخزين هوياتٍ لم يتحقّق منها أحد.
    """
    src = (ROOT / "db/schema_visitors.py").read_text(encoding="utf-8")
    block = src.split("CREATE TABLE IF NOT EXISTS visitors")[1].split(");")[0]
    for banned in ("id_number", "national_id", "iqama", "passport"):
        assert banned not in block.lower(), "جدول الزوّار يخزّن %s" % banned
