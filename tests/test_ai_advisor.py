#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tests/test_ai_advisor.py — الرؤى الذكية: مستشارٌ يقرأ الأرقام لا الأسماء

`/api/ai/analyze` كان مبنيّاً ويعمل منذ دفعاتٍ **بلا شاشةٍ تناديه** —
نفس علّة `staff-login`. وحين رُبط، كشفت المراجعة خمس علل فيه:

    ١ نموذجٌ قديم              `claude-opus-4-5`
    ٢ عميل **متزامن** في `async` — يُجمّد الخادم لكل المستأجرين
    ٣ `max_tokens=1024`         يقطع الجواب في منتصفه
    ٤ `str(e)` يُعاد للعميل     يكشف مسارات الملفات وربما المفتاح
    ٥ `require_client`          يفتح إيرادات المنشأة لموظف الاستقبال

المخاطر التي يحرسها هذا الملف:

    ١ بيانات نزيلٍ تُرسَل إلى نموذجٍ خارجي
    ٢ نداءٌ متزامن يُجمّد المنصة
    ٣ سؤالٌ بلا حدّ يستنزف رصيد المنصة
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ADVISOR = ROOT / "routes/ai_advisor.py"
UI_JS = ROOT / "static/dheuof/modules/12-analytics/js/advisor.js"
UI_HTML = ROOT / "static/dheuof/modules/12-analytics/index.html"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def code_only(path: Path) -> str:
    """
    الملف بلا وثائقه ولا تعليقاته.

    وثائق `ai_advisor.py` تذكر العلل القديمة (`claude-opus-4-5`،
    `max_tokens=1024`، `require_client`) عمداً لتشرح ما صُحّح — وفحصُ
    النصّ الخام يجعل كل شرحٍ جيدٍ يُسقط الاختبار.

    يُحذف كل تعبيرٍ نصّي مستقلّ **بمداه** من `ast` لا بمطابقة نصّه:
    `get_docstring` يُعيد النصّ مُهذَّب المسافات، فلا يُطابق الخام
    ويبقى منه سطرٌ يُسقط الاختبار.
    """
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    drop: set[int] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            drop.update(range(node.lineno - 1, (node.end_lineno or node.lineno)))
    return "\n".join(
        line.split("#")[0]
        for i, line in enumerate(lines)
        if i not in drop and not line.strip().startswith("#")
    )


# ── الخصوصية: لا يغادر اسمٌ ولا هوية ────────────────────────────
def test_snapshot_sends_counts_not_records():
    """
    اللقطة المُرسَلة أعدادٌ وإجماليات.

    تمرير صفوف النزلاء أو الحجوزات كما هي يُرسل أسماءً وأرقام هوية
    وجوالات إلى خدمةٍ خارجية — وهو أخطر تسريبٍ ممكن في هذا المستودع.
    """
    body = read(ADVISOR)
    section = body.split("def _snapshot")[1].split("\n@router")[0]
    for banned in ("id_number", "full_name", "absher_phone", "national_id",
                   "json.dumps(guests", "json.dumps(bookings"):
        assert banned not in section, "اللقطة تحمل %s" % banned
    # ما يُرسَل: أطوال ومجاميع
    assert "len(guests)" in section and "len(bookings)" in section


def test_prompt_body_contains_only_snapshot_and_question():
    """جسم الرسالة = اللقطة + سؤال المستخدم. لا صفوف ولا حقول."""
    body = read(ADVISOR)
    content = body.split('"content":')[1].split("}]")[0]
    assert "_snapshot(" in content
    assert "prompt" in content
    for banned in ("guests", "bookings", "invoices"):
        assert banned not in content, "جسم الرسالة يحمل %s" % banned


def test_snapshot_is_built_server_side():
    """
    الواجهة ترسل السؤال وحده.

    بناء اللقطة في المتصفّح يعني أنه يختار ما يُرسَل للنموذج، فيستطيع
    مُعدِّلٌ إرسال أسماء النزلاء بتغيير ملف جافاسكربت.
    """
    js = read(UI_JS)
    assert "JSON.stringify({ prompt: text })" in js
    for banned in ("get_guests", "id_number", "full_name", "/api/guests"):
        assert banned not in js, "الواجهة تلمس %s" % banned


def test_ui_states_the_privacy_rule_to_the_user():
    """التصريح جزءٌ من الميزة: الغياب يترك المستخدم يخمّن."""
    assert "لا أسماء نزلاء" in read(UI_HTML)


# ── العلل الخمس التي صُحّحت ─────────────────────────────────────
def test_model_is_current():
    """
    `claude-opus-4-5` نموذجٌ من جيلٍ سابق. الجيل الحالي `claude-opus-5`.
    """
    body = code_only(ADVISOR)
    assert 'MODEL = "claude-opus-5"' in body
    assert "claude-opus-4-5" not in body


def test_client_is_async():
    """
    عميلٌ متزامن داخل مسار `async` يحجز حلقة الأحداث طوال انتظار الردّ
    — فتتجمّد المنصة لكل المستأجرين، لا لصاحب السؤال وحده.
    """
    body = code_only(ADVISOR)
    assert "anthropic.AsyncAnthropic(" in body
    assert "anthropic.Anthropic(" not in body.replace("anthropic.AsyncAnthropic(", "")
    assert "await client.messages.create(" in body


def test_max_tokens_is_not_lowballed():
    """`1024` يقطع الجواب في منتصفه فيعود المستخدم بسؤالٍ ثانٍ — وتكلفةٍ ثانية."""
    body = code_only(ADVISOR)
    assert "MAX_TOKENS = 16000" in body
    assert "max_tokens=1024" not in body


def test_exception_text_never_reaches_the_client():
    """
    نصّ الخطأ يُسجَّل ولا يُعاد: يحمل مسارات ملفاتٍ وربما جزءاً من
    المفتاح، وإعادته للعميل تسريبٌ لا تشخيص.
    """
    body = read(ADVISOR)
    tree = ast.parse(body)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or not isinstance(node.exc, ast.Call):
            continue
        rendered = ast.unparse(node.exc)
        if "HTTPException" not in rendered:
            continue
        assert "str(exc)" not in rendered and "str(e)" not in rendered, \
            "نصّ الاستثناء يُعاد للعميل: %s" % rendered[:80]


def test_route_requires_manager_not_any_staff():
    """
    الرؤى تقرأ إيرادات المنشأة وإشغالها — ليست شاشةَ موظف استقبال.
    """
    assert "from db.access import require_manager" in code_only(ADVISOR)
    assert "require_client" not in code_only(ADVISOR)

    # الحرّاس يُفحصون على المصدر الأصلي: `code_only` يحذف الوثائق
    # فتختلّ أرقام الأسطر التي يعتمدها `get_source_segment`.
    body = read(ADVISOR)
    tree = ast.parse(body)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") in
                   ("get", "post") for d in node.decorator_list):
            continue
        section = ast.get_source_segment(body, node) or ""
        assert "require_manager(request)" in section, "%s بلا حارس" % node.name


# ── الحدّ والتكلفة ──────────────────────────────────────────────
def test_rate_limit_exists_and_is_per_tenant():
    """
    كل سؤال يكلّف مالاً. بلا حدّ يستهلك موظفٌ واحد رصيد المنصة كلّه،
    أو يُبقي زرّاً مضغوطاً فيُنشئ فاتورةً بلا سقف.
    """
    body = read(ADVISOR)
    assert "RATE_PER_HOUR" in body
    section = body.split("def _rate_ok")[1].split("\nSYSTEM_PROMPT")[0]
    assert "client_id" in section, "الحدّ ليس لكل منشأة"
    assert "429" in body


def test_rate_bucket_is_pruned():
    """
    قاموسٌ ينمو بعدد المنشآت التي سألت منذ الإقلاع = تسريب ذاكرةٍ بطيء.
    """
    section = read(ADVISOR).split("def _rate_ok")[1].split("\nSYSTEM_PROMPT")[0]
    assert "pop(" in section


def test_prompt_length_is_bounded():
    """سؤالٌ بلا حدّ يجعل طلباً واحداً يكلّف كثيراً."""
    body = read(ADVISOR)
    assert "MAX_PROMPT" in body and "len(prompt) > MAX_PROMPT" in body


# ── متانة التشغيل ───────────────────────────────────────────────
def test_import_comes_after_the_key_check():
    """
    بيئةٌ بلا الحزمة يجب أن تُعيد «الخدمة غير مُفعَّلة» لا ٥٠٠ غامضاً.

    وقع هذا فعلاً: `import anthropic` كان أول سطرٍ في الدالة، فانهار
    المسار قبل أن يفحص المفتاح.
    """
    body = read(ADVISOR)
    section = body.split("async def ask")[1]
    key_at = section.index("if not cfg.anthropic_api_key")
    import_at = section.index("import anthropic")
    assert key_at < import_at, "الاستيراد قبل فحص المفتاح"
    assert "except ImportError" in section


def test_requirements_pin_supports_the_features_used():
    """
    `anthropic>=0.28.0` يسمح بنسخةٍ لا تعرف `AsyncAnthropic` ولا
    `thinking: adaptive` — فيُثبَّت شيءٌ يفشل عند أول نداء.
    """
    reqs = read(ROOT / "requirements.txt")
    line = next(x for x in reqs.splitlines() if x.startswith("anthropic"))
    version = re.search(r">=\s*(\d+)\.", line)
    assert version and int(version.group(1)) >= 1, "الحدّ الأدنى أقدم من ١.x: %s" % line


def test_adaptive_thinking_not_budget_tokens():
    """
    `budget_tokens` مُزال على هذا الجيل ويُرفض بـ٤٠٠. البديل
    `thinking: {type: adaptive}`.
    """
    body = code_only(ADVISOR)
    assert '"type": "adaptive"' in body
    assert "budget_tokens" not in body


def test_refusal_and_truncation_are_handled():
    """`stop_reason` يُفحص: قراءة `content` قبله تُنتج جواباً فارغاً بلا سبب."""
    body = read(ADVISOR)
    assert 'stop_reason == "refusal"' in body
    assert '"max_tokens"' in body


# ── الشاشة موصولة وحقيقية ───────────────────────────────────────
@pytest.mark.parametrize("endpoint", ["/api/insights/status", "/api/insights/ask"])
def test_ui_calls_the_real_endpoints(endpoint):
    """واجهةٌ بلا نداء API ليست واجهة."""
    assert endpoint in read(UI_JS)


def test_page_loads_the_script_once():
    """
    أُدرج الوسم أول مرة باستبدال `</body>` أعمى، فوقع **داخل نصّ
    جافاسكربت** يبني صفحة طباعة — فكسر تحليل الملف كلّه.
    """
    assert read(UI_HTML).count("advisor.js") == 1


def test_ui_init_waits_for_dom():
    assert "DOMContentLoaded" in read(UI_JS)


def test_ui_escapes_the_model_answer():
    """
    جواب النموذج نصٌّ خارجي يُحقن في الصفحة — يُهرَّب كأي مُدخَل.
    """
    js = read(UI_JS)
    assert "function esc(" in js
    for line in js.splitlines():
        code = line.split("//")[0]
        if "'<" not in code and '"<' not in code:
            continue
        for token in re.findall(r"\+\s*([a-zA-Z_$][\w.$]*)\s*(?:\+|;|\)|,|$)", code):
            assert token.split(".")[0] in ("esc", "encodeURIComponent", "Number",
                                           "String", "Math", "JSON"), \
                "قيمة غير مُهرَّبة: %s" % code.strip()[:70]


# ── الشيفرة الميتة التي حُذفت لا تعود ───────────────────────────
@pytest.mark.parametrize("column", ["chatbot_config", "whatsapp_config", "review_settings"])
def test_dead_columns_stay_deleted(column):
    """
    ثلاثة أعمدة كانت تُكتب في كل حفظِ منشأة ولا تُقرأ في موضعٍ واحد.
    """
    for path in (ROOT / "db/store.py", ROOT / "db/migrations.py"):
        assert column not in read(path), "%s عاد في %s" % (column, path.name)


def test_old_ai_route_stays_deleted():
    """`/api/ai/analyze` استُبدل بـ`/api/insights/*` — لا يبقى الاثنان."""
    body = read(ROOT / "routes/system.py")
    assert "/api/ai/analyze" not in body
    assert "anthropic" not in body
