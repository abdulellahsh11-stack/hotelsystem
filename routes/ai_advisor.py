#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/ai_advisor.py — الرؤى الذكية: مستشارٌ فندقي يقرأ أرقام منشأتك

كان هذا المسار في `routes/system.py` بلا واجهة تناديه — مبنيٌّ ويعمل
ولا باب له، كما كان `staff-login`. وفيه أربع علل صُحّحت هنا:

    ١ نموذجٌ قديم `claude-opus-4-5` → `claude-opus-5`
    ٢ عميلٌ **متزامن** داخل مسار `async` — يُجمّد الخادم لكل المستأجرين
      طوال ثوانٍ عند كل سؤال. صار `AsyncAnthropic`.
    ٣ `max_tokens=1024` يقطع الجواب في منتصفه → ١٦٠٠٠
    ٤ `str(e)` يُعاد للعميل — يكشف مسارات الملفات وربما جزءاً من المفتاح

**لا تُرسَل بيانات نزيلٍ إلى النموذج.** ما يُرسَل أعدادٌ وإجماليات:
«١٢ نزيلاً · ٨ حجوزات · إيراد ٢٤٠٠٠». الاسم ورقم الهوية والجوال لا
تغادر قاعدة البيانات — والسؤال الذي يُجاب بأعدادٍ لا يحتاج أسماء.
"""
from __future__ import annotations

import logging
import time
from threading import Lock

from fastapi import APIRouter, HTTPException, Request

from db.access import require_manager

router = APIRouter(prefix="/api/insights", tags=["Insights"])
log = logging.getLogger("dheuof.insights")

MODEL = "claude-opus-5"
MAX_TOKENS = 16000
MAX_PROMPT = 2000

#: حدُّ معدّلٍ لكل منشأة — كل سؤال يكلّف مالاً حقيقياً.
#
# بلا حدّ يستطيع موظفٌ واحد أن يستهلك رصيد المنصة كلّه في دقائق، أو
# يُبقي زرّاً مضغوطاً فيُنشئ فاتورةً لا سقف لها.
RATE_PER_HOUR = 30
_asked: dict[str, list[float]] = {}
_lock = Lock()


def _rate_ok(client_id: str) -> tuple[bool, int]:
    """هل بقي لهذه المنشأة رصيدٌ في ساعتها؟ يُعيد (مسموح، المتبقّي)."""
    now = time.time()
    with _lock:
        hits = [t for t in _asked.get(client_id, []) if now - t < 3600]
        if len(hits) >= RATE_PER_HOUR:
            _asked[client_id] = hits
            return False, 0
        hits.append(now)
        _asked[client_id] = hits
        # تنظيفٌ دوري: كل منشأة تسأل مرةً تُضيف مفتاحاً لا يُحذف أبداً
        if len(_asked) > 5000:
            for key in [k for k, v in _asked.items() if not v or now - max(v) >= 3600]:
                _asked.pop(key, None)
        return True, RATE_PER_HOUR - len(hits)


SYSTEM_PROMPT = (
    "أنت مستشارٌ فندقي خبير في السوق السعودي، تنصح مالك منشأةٍ يقرأ "
    "أرقامه. أجب بالعربية، مباشرةً وبإيجاز، وبخطواتٍ قابلة للتنفيذ.\n\n"
    "قواعد لا تُخالَف:\n"
    "• استند إلى الأرقام المعطاة وحدها. لا تخترع رقماً لم يُعطَ لك.\n"
    "• إن كانت الأرقام لا تكفي للإجابة، قل ذلك وحدّد ما ينقصك.\n"
    "• لا تطلب بيانات نزيلٍ بعينه — لا تصلك ولن تصلك."
)


def _snapshot(request: Request, client_id: str) -> str:
    """
    لقطةٌ رقمية من بيانات المنشأة — أعدادٌ وإجماليات لا أسماء.

    تُبنى هنا لا في الواجهة: بناؤها هناك يعني أن المتصفّح يختار ما
    يُرسَل للنموذج، فيستطيع مُعدِّلٌ إرسال أسماء النزلاء بتغيير جافاسكربت.
    """
    store = request.app.state.store
    try:
        bookings = store.get_bookings(client_id) or []
        guests = store.get_guests(client_id) or []
        invoices = store.get_invoices(client_id) or []
    except Exception as exc:
        log.warning("تعذّر بناء لقطة المنشأة %s: %s", client_id, exc)
        return "لا بيانات متاحة"

    def _total(rows, *keys):
        out = 0.0
        for row in rows:
            for key in keys:
                value = (row or {}).get(key)
                if value not in (None, ""):
                    try:
                        out += float(value)
                    except (TypeError, ValueError):
                        pass
                    break
        return out

    statuses: dict[str, int] = {}
    for booking in bookings:
        state = str((booking or {}).get("status") or "غير محدد")
        statuses[state] = statuses.get(state, 0) + 1

    lines = [
        f"عدد النزلاء المسجَّلين: {len(guests)}",
        f"عدد الحجوزات: {len(bookings)}",
        f"عدد الفواتير: {len(invoices)}",
        f"إجمالي قيمة الفواتير: {_total(invoices, 'total', 'amount', 'total_amount'):.2f} ر.س",
        f"إجمالي قيمة الحجوزات: {_total(bookings, 'total_amount', 'total_price', 'amount'):.2f} ر.س",
    ]
    if statuses:
        lines.append("حالات الحجوزات: " +
                     " · ".join(f"{k}: {v}" for k, v in sorted(statuses.items())))
    return "\n".join(lines)


@router.get("/status")
async def insights_status(request: Request):
    """
    هل الخدمة مُفعَّلة؟ تسأله الواجهة قبل أن تعرض الزرّ.

    عرضُ زرٍّ يفشل عند الضغط أسوأ من إخفائه: المستخدم يظنّ العطل في
    منشأته لا في إعدادٍ ناقص.
    """
    session = require_manager(request)
    enabled = bool(request.app.state.cfg.anthropic_api_key)
    with _lock:
        used = len([t for t in _asked.get(session["client_id"], [])
                    if time.time() - t < 3600])
    return {"success": True, "data": {
        "enabled": enabled,
        "remaining": max(0, RATE_PER_HOUR - used),
        "hourly_limit": RATE_PER_HOUR,
        "note": None if enabled else
                "أضف ANTHROPIC_API_KEY في متغيّرات البيئة لتفعيل الرؤى",
    }}


@router.post("/ask")
async def ask(request: Request):
    """
    سؤالٌ عن أرقام المنشأة.

    `require_manager` لا `require_client`: الرؤى تقرأ إيرادات المنشأة
    وإشغالها — ليست شاشةَ موظف استقبال.
    """
    session = require_manager(request)
    cid = session["client_id"]
    cfg = request.app.state.cfg

    if not cfg.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="خدمة الرؤى غير مُفعَّلة — أضف ANTHROPIC_API_KEY",
        )

    # الاستيراد بعد فحص المفتاح: وضعُه قبله يجعل بيئةً بلا الحزمة تُعيد
    # ٥٠٠ غامضاً بدل «الخدمة غير مُفعَّلة» — وهو ما وقع فعلاً هنا.
    try:
        import anthropic
    except ImportError:
        log.error("حزمة anthropic غير مثبَّتة — راجع requirements.txt")
        raise HTTPException(
            status_code=503, detail="خدمة الرؤى غير متاحة في هذا التثبيت"
        ) from None

    data = await request.json()
    prompt = str(data.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="اكتب سؤالك أولاً")
    if len(prompt) > MAX_PROMPT:
        raise HTTPException(
            status_code=400, detail=f"السؤال أطول من {MAX_PROMPT} حرف"
        )

    allowed, remaining = _rate_ok(cid)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=f"بلغت حدّ {RATE_PER_HOUR} سؤالاً في الساعة — عد بعد قليل",
        )

    # عميلٌ **غير متزامن**: العميل المتزامن داخل مسار `async` يحجز حلقة
    # الأحداث طوال انتظار الردّ، فتتجمّد المنصة لكل المستأجرين — لا
    # لصاحب السؤال وحده.
    client = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
    try:
        message = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"أرقام المنشأة:\n{_snapshot(request, cid)}\n\nالسؤال: {prompt}",
            }],
        )
    except anthropic.RateLimitError:
        raise HTTPException(
            status_code=429, detail="الخدمة مزدحمة — أعد المحاولة بعد دقيقة"
        ) from None
    except anthropic.AuthenticationError:
        log.error("مفتاح ANTHROPIC_API_KEY مرفوض")
        raise HTTPException(
            status_code=503, detail="مفتاح الخدمة غير صالح — راجع الإعدادات"
        ) from None
    except anthropic.APIConnectionError:
        raise HTTPException(
            status_code=503, detail="تعذّر الوصول للخدمة — أعد المحاولة"
        ) from None
    except anthropic.APIStatusError as exc:
        # الرسالة تُسجَّل ولا تُعاد: نصّ الخطأ يحمل مسارات ملفاتٍ وربما
        # جزءاً من المفتاح، وإعادته للعميل تسريبٌ لا تشخيص.
        log.error("خطأ في خدمة الرؤى (%s): %s", exc.status_code, exc, exc_info=True)
        raise HTTPException(status_code=502, detail="تعذّر إتمام الطلب") from None

    if message.stop_reason == "refusal":
        raise HTTPException(
            status_code=422, detail="تعذّرت الإجابة عن هذا السؤال — أعد صياغته"
        )

    answer = "\n".join(b.text for b in message.content if b.type == "text").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="جاء ردٌّ فارغ — أعد المحاولة")

    log.info("سؤال رؤى للمنشأة %s (%s رمزاً)", cid, message.usage.output_tokens)
    return {"success": True, "data": {
        "answer": answer,
        "remaining": remaining,
        "truncated": message.stop_reason == "max_tokens",
    }}
