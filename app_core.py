#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_core.py — قلب التطبيق: الإعداد، الـ middleware، المصادقة
يُستورد من main.py (نقطة الدخول لـ uvicorn)
"""

import decimal
import hashlib
import json
import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles


class _SafeEncoder(json.JSONEncoder):
    """Serialize PostgreSQL Decimal/date/datetime types that json.dumps rejects."""
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger("dheuof")

# ──────────────────────────────────────────────────────────────
#  Sessions (in-memory; reset on restart — fine for stateless Railway)
# ──────────────────────────────────────────────────────────────
_admin_sessions: dict = {}   # token → {"created_at": ...}
_client_sessions: dict = {}  # token → {"client_id": ..., "created_at": ...}
_lock = threading.Lock()

# Secure cookies in production (HTTPS). Railway/most PaaS set these env vars.
_COOKIE_SECURE = bool(
    os.environ.get("RAILWAY_ENVIRONMENT")
    or os.environ.get("RAILWAY_STATIC_URL")
    or os.environ.get("COOKIE_SECURE", "").lower() in ("1", "true", "yes")
)

# M3 mitigation: حدّ بسيط لمعدّل التسجيل لكل IP (ضد إنشاء حسابات بالجملة)
_reg_attempts: dict = {}     # ip → [timestamps]
_REG_MAX_PER_HOUR = int(os.environ.get("REG_MAX_PER_HOUR", "5"))

# Login rate limiting: protect /api/login against brute-force attacks
_login_attempts: dict = {}   # ip → [timestamps]
_LOGIN_MAX_PER_MINUTE = int(os.environ.get("LOGIN_MAX_PER_MINUTE", "10"))


# خلف وسيطٍ عكسي (Railway وأمثاله) يكون `request.client.host` عنوان
# الوسيط نفسه لكل الطلبات — فيتشارك كل المستأجرين دلواً واحداً: عشر
# محاولات دخول في الدقيقة تُغلق المنصة على الجميع. وuvicorn لا يثق بترويسة
# X-Forwarded-For إلا من 127.0.0.1 افتراضياً، والوسيط ليس كذلك.
#
# المقايضة صريحة: الوثوق بالترويسة يسمح بانتحال العنوان للتهرّب من الحدّ،
# وعدمُ الوثوق يسمح بإغلاق المنصة على الجميع. الثاني أسوأ — تعطيلٌ تامّ
# بعشرة طلبات — فالافتراض هو الوثوق بقفزةٍ واحدة، ويُطفأ بـTRUST_PROXY=0
# عند التشغيل بلا وسيط.
TRUST_PROXY = os.environ.get("TRUST_PROXY", "1") not in ("0", "false", "False", "")
try:
    TRUST_PROXY_HOPS = max(1, int(os.environ.get("TRUST_PROXY_HOPS", "1")))
except ValueError:
    TRUST_PROXY_HOPS = 1


def client_ip(request) -> str:
    """
    عنوان الطالب الحقيقي لأغراض حدّ المعدّل.

    يُؤخذ من X-Forwarded-For بعدّ القفزات من اليمين: الوسيط يُلحق العنوان
    الحقيقي في آخر القائمة، وما قبله يكتبه العميل فيمكن انتحاله.
    """
    if TRUST_PROXY:
        forwarded = request.headers.get("x-forwarded-for", "")
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            index = max(0, len(parts) - TRUST_PROXY_HOPS)
            return parts[index]
    return request.client.host if request.client else "?"


def _reg_rate_ok(ip: str) -> bool:
    """يسمح بحد أقصى REG_MAX_PER_HOUR تسجيلات لكل IP في الساعة."""
    now = datetime.now().timestamp()
    with _lock:
        _prune_attempts(_reg_attempts, now, 3600)
        hits = [t for t in _reg_attempts.get(ip, []) if now - t < 3600]
        if len(hits) >= _REG_MAX_PER_HOUR:
            _reg_attempts[ip] = hits
            return False
        hits.append(now)
        _reg_attempts[ip] = hits
        return True


# حدٌّ يُشغّل التنظيف. كل عنوان جديد يضيف مفتاحاً لا يُحذف أبداً، فالقاموس
# ينمو بعدد العناوين التي زارت المنصة منذ آخر إعادة تشغيل — تسريبُ ذاكرةٍ
# بطيء يستغلّه من يوزّع محاولاته على عناوين كثيرة.
_ATTEMPTS_PRUNE_THRESHOLD = 10_000


def _prune_attempts(bucket: dict, now: float, window: int) -> None:
    """يحذف المفاتيح التي انقضت نافذتها. يُستدعى تحت القفل."""
    if len(bucket) < _ATTEMPTS_PRUNE_THRESHOLD:
        return
    for key in [k for k, v in bucket.items() if not v or now - max(v) >= window]:
        bucket.pop(key, None)


def _login_rate_ok(ip: str) -> bool:
    """Allow at most LOGIN_MAX_PER_MINUTE login attempts per IP per minute (brute-force guard)."""
    now = datetime.now().timestamp()
    with _lock:
        _prune_attempts(_login_attempts, now, 60)
        hits = [t for t in _login_attempts.get(ip, []) if now - t < 60]
        if len(hits) >= _LOGIN_MAX_PER_MINUTE:
            _login_attempts[ip] = hits
            return False
        hits.append(now)
        _login_attempts[ip] = hits
        return True


def _new_token() -> str:
    return secrets.token_urlsafe(32)


# عدد دورات PBKDF2.
#   LEGACY — ما بُنيت به كل التجزئات القائمة. يبقى للتحقق منها فقط.
#   CURRENT — توصية OWASP لـ PBKDF2-SHA256؛ يُستخدم لكل تجزئة جديدة.
# لا تُرفع LEGACY: رفعه يمنع كل عميل قائم من الدخول لأن تجزئته العارية
# لا تحمل عدد دوراتها. الترقية تتم فرداً فرداً عند أول دخول ناجح.
PBKDF2_ITERATIONS_LEGACY = 100_000
PBKDF2_ITERATIONS_CURRENT = 600_000

_HASH_PREFIX = "pbkdf2_sha256"


def _hash_password(password: str, salt: str,
                   iterations: int = PBKDF2_ITERATIONS_LEGACY) -> str:
    """
    يُعيد تجزئة عارية (hex) بلا وسم.

    الافتراضي يبقى LEGACY عمداً: مسارات المشرف تقارن ناتج هذه الدالة
    بتجزئات مخزَّنة قديمة، فتغيير الافتراضي يكسر دخول المشرف صامتاً.
    """
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), iterations
    ).hex()


def _make_password(password: str) -> tuple[str, str]:
    """
    يُنشئ ملحاً فريداً ويعيد (تجزئة مُوسَّمة، ملح).

    الصيغة `pbkdf2_sha256$<دورات>$<hex>` تحمل عدد دوراتها معها، فترفع
    المنصة العدد مستقبلاً دون إبطال ما هو مخزَّن.
    """
    salt = secrets.token_hex(16)
    digest = _hash_password(password, salt, PBKDF2_ITERATIONS_CURRENT)
    return f"{_HASH_PREFIX}${PBKDF2_ITERATIONS_CURRENT}${digest}", salt


def _parse_stored_hash(stored: str) -> tuple[int, str]:
    """يُفكّك المخزَّن إلى (دورات، تجزئة). العاري يُعامَل كقديم."""
    if stored.startswith(_HASH_PREFIX + "$"):
        try:
            _, iters, digest = stored.split("$", 2)
            return int(iters), digest
        except (ValueError, TypeError):
            pass  # مُشوَّه — يسقط إلى القديم فيفشل التحقق بأمان
    return PBKDF2_ITERATIONS_LEGACY, stored


def _verify_password(password: str, client: dict, cfg) -> bool:
    """يتحقق بملح الحساب، ويقبل الصيغتين المُوسَّمة والعارية القديمة."""
    stored = client.get("pass_hash", "") or ""
    if not stored:
        return False
    salt = client.get("pass_salt") or cfg.pass_salt   # legacy fallback
    iterations, digest = _parse_stored_hash(stored)
    return secrets.compare_digest(
        _hash_password(password, salt, iterations), digest
    )


def password_needs_upgrade(stored: str) -> bool:
    """هل التجزئة المخزَّنة أضعف من المعيار الحالي؟"""
    iterations, _ = _parse_stored_hash(stored or "")
    return iterations < PBKDF2_ITERATIONS_CURRENT


# ──────────────────────────────────────────────────────────────
#  Lifespan — startup / shutdown
# ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app_: FastAPI):
    from config import Config, init_config
    from db.connection import init_db
    from db.store import DataStore

    cfg = Config.from_env()
    init_config(cfg)
    log.info(cfg.summary())

    os.makedirs("data", exist_ok=True)
    db = init_db(cfg.database_url, "data/store.json")
    store = DataStore(db, cfg.dual_write)

    app_.state.cfg = cfg
    app_.state.db = db
    app_.state.store = store

    # ── v3 migrations — جميع الوحدات الـ 15 + وجهات سياحية ──
    try:
        from db.migrations import run_all_migrations
        run_all_migrations(db)
    except Exception as e:
        log.warning(f"v1 migrations: {e}")
    try:
        from db.schema_v3 import run_v3_migrations
        run_v3_migrations(db)
    except Exception as e:
        log.warning(f"v3 migrations: {e}")
    try:
        from db.schema_v3 import run_staff_app_migrations
        run_staff_app_migrations(db)
    except Exception as e:
        log.warning(f"staff_app migrations: {e}")
    try:
        from db.schema_services import run_services_migration
        run_services_migration(db)
    except Exception as e:
        log.warning(f"services migration: {e}")
    try:
        from db.schema_alerts import run_alerts_migration
        run_alerts_migration(db)
    except Exception as e:
        log.warning(f"alerts migration: {e}")
    # RLS: تُطبَّق السياسات عند الإقلاع حين يُطلب ذلك صراحةً. تحتاج
    # مستخدماً يملك الجداول، فتُشغَّل مرة ثم يُحوَّل الاتصال إلى دور
    # التطبيق. لا تعمل تلقائياً: تطبيقها بلا الخطوتين الأخريين يوقف
    # المنصة.
    if os.environ.get("RLS_APPLY_ON_STARTUP", "").lower() in ("1", "true", "yes"):
        try:
            from db.rls import enable_rls
            result = enable_rls(db)
            log.info("RLS: طُبّقت على %s", ", ".join(result["applied"]) or "لا شيء")
        except Exception as e:
            log.error("فشل تطبيق RLS: %s", e)
    try:
        from db.schema_v3 import run_security_hardening
        run_security_hardening(db)
    except Exception as e:
        log.warning(f"security hardening migrations: {e}")
    try:
        from db.schema_v3 import run_sessions_migration
        run_sessions_migration(db)
    except Exception as e:
        log.warning(f"sessions migration: {e}")
    try:
        from db.schema_room_map import run_room_map_migration
        run_room_map_migration(db)
    except Exception as e:
        log.warning(f"room map migration: {e}")
    try:
        from db.schema_guest_crypto import run_guest_crypto_migration
        run_guest_crypto_migration(db)
    except Exception as e:
        log.warning(f"guest crypto migration: {e}")
    try:
        from routes.leads import ensure_schema as _leads_schema
        _leads_schema(db)
    except Exception as e:
        log.warning(f"leads migration: {e}")
    try:
        from db.schema_v3 import run_rls_migration
        run_rls_migration(db)
    except Exception as e:
        log.warning(f"RLS migration: {e}")
    try:
        from db.schema_v3 import run_perf_indexes
        run_perf_indexes(db)
        log.info("✓ Performance indexes ready")
    except Exception as e:
        log.warning(f"perf indexes: {e}")
    try:
        from db.schema_v3 import run_v4_migrations
        run_v4_migrations(db)
        log.info("✓ v4 migrations (ZATCA + Night Audit + Reviews) ready")
    except Exception as e:
        log.warning(f"v4 migrations: {e}")
    try:
        from db.schema_visitors import run_visitor_migrations
        run_visitor_migrations(db)
        log.info("✓ جداول الزوّار جاهزة")
    except Exception as e:
        log.warning(f"جداول الزوّار: {e}")
    try:
        from db.schema_listings import run_listing_migrations
        run_listing_migrations(db)
        log.info("✓ جداول العرض والبحث جاهزة")
    except Exception as e:
        log.warning(f"جداول العرض: {e}")

    # ── Sentry (APM / error tracking) ──────────────────────────────────────
    if cfg.has_sentry:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=cfg.sentry_dsn,
                traces_sample_rate=0.1,
                environment="production" if not cfg.debug else "development",
            )
            log.info("✓ Sentry initialized")
        except Exception as e:
            log.warning(f"Sentry init failed: {e}")

    # Load optional services — each independent so one failure doesn't sink the rest
    app_.state.pricing = None
    app_.state.channels = None
    app_.state.api_keys = None
    app_.state.zatca = None
    try:
        from services.dynamic_pricing import DynamicPricingEngine
        app_.state.pricing = DynamicPricingEngine(db)
        log.info("✓ Dynamic Pricing service")
    except Exception as e:
        log.warning(f"Dynamic Pricing unavailable: {e}")
    try:
        from services.channel_manager import ChannelManager
        app_.state.channels = ChannelManager(db)
        log.info("✓ Channel Manager service")
    except Exception as e:
        log.warning(f"Channel Manager service unavailable: {e}")
    try:
        from services.api_keys import APIKeyManager
        app_.state.api_keys = APIKeyManager(db)
        log.info("✓ API Key Manager service")
    except Exception as e:
        log.warning(f"API Key Manager unavailable: {e}")
    try:
        from services.zatca import ZatcaInvoiceService
        app_.state.zatca = ZatcaInvoiceService(db)
        log.info("✓ ZATCA Invoice service")
    except Exception as e:
        log.warning(f"ZATCA service unavailable: {e}")

    # ── Background session cleanup (every 6 hours) ─────────────────────────
    import asyncio

    async def _session_cleanup():
        while True:
            await asyncio.sleep(6 * 3600)
            try:
                if db.use_postgres:
                    db.execute("DELETE FROM client_sessions WHERE expires_at < NOW()")
                    # Also clear expired from in-memory dict
                    with _lock:
                        stale = [t for t, s in list(_client_sessions.items())
                                 if s.get("created_at", "9999") < (datetime.now() - timedelta(days=8)).isoformat()]
                        for t in stale:
                            _client_sessions.pop(t, None)
                    log.info("✅ Session cleanup completed")
            except Exception as e:
                log.warning(f"Session cleanup error: {e}")

    _cleanup_task = asyncio.create_task(_session_cleanup())

    yield

    _cleanup_task.cancel()
    db.close()


# ──────────────────────────────────────────────────────────────
#  App
# ──────────────────────────────────────────────────────────────
app = FastAPI(title="ضيوف — Dheuof Hotel SaaS", version="3.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)

# M4 fix: قصر CORS على نطاقات ضيوف المعروفة بدل "*" مع بقاء credentials
_ALLOWED_ORIGINS = [o.strip() for o in os.environ.get(
    "CORS_ORIGINS",
    "https://www.dheuof.com,https://dheuof.com,http://localhost:5050,http://127.0.0.1:5050",
).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.middleware("http")
async def bind_tenant_context(request: Request, call_next):
    """
    يربط مستأجر الطلب بسياق التنفيذ، فتقرأه طبقة الاتصال وتضبطه داخل
    معاملة كل استعلام (RLS).

    يُقرأ من الجلسة على الخادم لا من أي مُدخل. وهذه هي النقطة الوحيدة
    التي تُحدَّد فيها هوية المستأجر لعمر الطلب.

    التنظيف في finally شرط لا احتياط: خيوط الخادم مُعاد استعمالها،
    وسياقٌ يبقى بعد الطلب يُورَّث لطلب منشأة أخرى.
    """
    from db.tenant_context import clear_tenant, set_tenant

    try:
        session = get_client_session(request)
    except Exception:
        session = None

    set_tenant((session or {}).get("client_id"))
    try:
        return await call_next(request)
    finally:
        clear_tenant()


async def _stamp_html_response(response):
    """
    يقرأ جسم صفحة HTML ويُلحق بصمة الإصدار بمراجع الملفات الثابتة.

    الجسم يُجمَّع في الذاكرة لأن التعديل يحتاج النصّ كاملاً — وصفحات
    هذه المنصة عشرات الكيلوبايتات لا أكثر. أي فشل يُعيد الاستجابة كما
    هي: صفحةٌ بلا بصمة أهون من صفحةٍ لا تُعرض.
    """
    from starlette.responses import Response as _Response

    # لا يُلمس جسمٌ مُرمَّز (gzip وأمثاله): فكُّه كنصّ يفشل، وقد استُهلك
    # المُكرِّر حينها فتخرج الصفحة **فارغة**. وهذا وقع فعلاً في الإنتاج:
    # curl لا يطلب الضغط افتراضياً فبدا كل شيء سليماً، والمتصفّح يطلبه
    # دائماً فرأى المستخدم صفحةً بيضاء.
    if response.headers.get("content-encoding"):
        return response

    chunks: list = []
    try:
        if hasattr(response, "body_iterator"):
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, bytes) else str(chunk).encode())
            body = b"".join(chunks)
        else:
            body = response.body or b""
        if not body:
            return response
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            # ليس نصّاً — يُعاد كما هو بدل أن يضيع
            from starlette.responses import Response as _Raw

            headers = {k: v for k, v in response.headers.items()
                       if k.lower() != "content-length"}
            return _Raw(content=body, status_code=response.status_code,
                        headers=headers, media_type=response.media_type)

        from services.asset_version import stamp_html

        stamped = stamp_html(text).encode("utf-8")
        headers = {k: v for k, v in response.headers.items()
                   if k.lower() != "content-length"}
        return _Response(content=stamped, status_code=response.status_code,
                         headers=headers, media_type=response.media_type)
    except Exception as exc:
        # الجسم قد يكون استُهلك بالفعل — إعادة `response` هنا تُخرج صفحةً
        # فارغة. يُعاد بناؤها ممّا جُمع، فأسوأ حالة صفحةٌ بلا بصمة.
        log.warning("تعذّر ختم صفحة HTML ببصمة الإصدار: %s", exc)
        if chunks:
            headers = {k: v for k, v in response.headers.items()
                       if k.lower() != "content-length"}
            return _Response(content=b"".join(chunks), status_code=response.status_code,
                             headers=headers, media_type=response.media_type)
        return response


@app.middleware("http")
async def add_security_and_cache_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path

    # ترويسات التخزين.
    #
    # كانت كل ملفات JS/CSS تُخدَم بـ`immutable` لسبعة أيام بلا بصمة في
    # عنوانها — و`immutable` تعني «لا تسأل عنه ثانيةً»، فيبقى المتصفّح
    # على نسخةٍ قديمة أسبوعاً بعد كل نشر. الآن `immutable` تُمنح فقط
    # لعنوانٍ يحمل البصمة الجارية، وهذا شرطُ صحّتها.
    from services.asset_version import cache_header

    response.headers["Cache-Control"] = cache_header(
        path, request.query_params.get("v"))

    # حقن البصمة في صفحات HTML: كل مرجع js/css فيها يخرج بـ`?v=`، فيتغيّر
    # عنوانه عند كل نشر ويُحمَّل الجديد حتماً. الصفحة نفسها لا تُخزَّن،
    # فهي التي تحمل البصمات الجديدة إلى المتصفّح.
    if (response.status_code == 200
            and "text/html" in response.headers.get("content-type", "")):
        response = await _stamp_html_response(response)
    # Security headers on all responses
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


# Module shortcut paths that must be locked behind login (server-side gate)
_PROTECTED_PAGE_PREFIXES = (
    "/dheuof", "/guests-module", "/shumus", "/tourism", "/inventory",
    "/warehouse", "/account", "/accounting", "/pos", "/smart-key", "/hr",
    "/channels", "/marketing-channels", "/analytics", "/staff",
    "/ota-bookings", "/trips", "/tourism-trips", "/guests", "/bookings",
)

# صفحات ثابتة محمية بمسارها الكامل. `dashboard.html` لوحة التحكم كاملةً،
# وكانت تُخدَم لأي زائر: الشرط القديم لم يكن يفحص إلا صفحات الوحدات.
_PROTECTED_STATIC_PAGES = ("/static/dashboard.html",)

# صفحات وحدات مفتوحة عمداً: بوابة النزيل يفتحها الضيف نفسه ولا جلسة
# منشأة له، فحجبها يمنع الغرض الذي بُنيت له.
_PUBLIC_MODULE_PAGES = ("/static/dheuof/modules/01-guests/portal.html",)


def _is_protected_page(path: str) -> bool:
    """
    هل هذا المسار صفحةَ برنامجٍ تحتاج جلسة؟

    الشرط السابق كان `path.endswith("/index.html")` — فكل صفحة وحدةٍ لا
    تُسمّى index (التسجيل · الاستقبال · المستخدمون) تُخدَم لأي زائر،
    وكذلك لوحة التحكم. الفحص الآن بالامتداد لا بالاسم.
    """
    if path in _PUBLIC_MODULE_PAGES:
        return False
    if path in _PROTECTED_STATIC_PAGES:
        return True
    if path.startswith("/static/dheuof/modules/") and path.endswith(".html"):
        return True
    # اختصارات المسارات: مطابقة تامّة أو مع شرطة مائلة ختامية
    return path in _PROTECTED_PAGE_PREFIXES or path.rstrip("/") in _PROTECTED_PAGE_PREFIXES


@app.middleware("http")
async def server_side_auth_gate(request: Request, call_next):
    """Real lock: serve program pages only to authenticated clients.

    Without a valid session, any direct navigation to a module page (either the
    pretty shortcut like /pos or the raw /static/dheuof/modules/<m>/index.html)
    is redirected to /login. This closes the gap where the client-side JS auth
    wall could be bypassed by disabling JavaScript or hitting the static file.
    """
    path = request.url.path
    if _is_protected_page(path):
        if get_client_session(request) is None:
            # Browsers navigating get a redirect; programmatic/XHR get 401
            accept = request.headers.get("accept", "")
            if "text/html" in accept:
                # إلى الصفحة الرئيسية لا صفحة الدخول: الزائر بلا جلسة
                # قد يكون عميلاً محتملاً، والرئيسية تُعرّفه بالمنصة
                # وتحمل الدخول والتسجيل معاً.
                return RedirectResponse("/", status_code=302)
            return JSONResponse({"detail": "غير مصرح — يلزم تسجيل الدخول"}, status_code=401)
    return await call_next(request)


# مسارات لها حدُّها الأضيق الخاصّ في هذا الملف — لا يُطبَّق الحدُّ العامّ
# عليها كي لا يُخفّف حمايتها (حدُّ الدخول أضيق بكثير من حدّ الكتابة العامّ).
_RATE_LIMIT_EXEMPT = frozenset({
    "/api/login", "/api/client/register", "/api/admin/login",
})


@app.middleware("http")
async def api_rate_limit(request: Request, call_next):
    """حدٌّ عامٌّ لطلبات الكتابة على الـ API ضد إغراق مجمّع الاتصالات.

    يحدُّ فقط طلبات الكتابة (POST/PUT/PATCH/DELETE) على `/api/*`، فالقراءة
    قليلة الكلفة والحجب الخاطئ لها أشدُّ إزعاجاً. المسارات ذات الحدّ الأضيق
    الخاصّ (الدخول والتسجيل) مستثناة كي لا يُضعِفها هذا الحدُّ الأوسع.

    التصنيف من **ذاكرة الجلسات وحدها** لا من قاعدة البيانات: لو استُعلمت
    القاعدة لاختيار المفتاح، لأمكن مهاجماً يُدوّر كوكيات جلسةٍ عشوائية أن
    يُجبر استعلاماً على المجمّع في كل طلب — أي أن الحارس يستهلك ما يحميه.

    وطبقتان لمن له جلسةٌ صالحة في الذاكرة: حدٌّ لكل جلسة (`WRITE_LIMIT`)
    كي لا يخنق موظفو منشأةٍ بعضهم، وسقفٌ أعلى لكل منشأة (`TENANT_LIMIT`)
    كي لا يُغرق مستأجرٌ المجمّعَ بفتح جلساتٍ كثيرة. المجهول بعنوانه
    (`ANON_LIMIT`)، والكوكي العشوائية لا تصيب الذاكرة فتقع في دلو العنوان.
    """
    if (request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/")
            and request.url.path not in _RATE_LIMIT_EXEMPT):
        from services import rate_limit

        token = _get_client_token(request)
        session = None
        if token:
            with _lock:
                session = _client_sessions.get(token)   # ذاكرة فقط — لا قاعدة
            # جلسةٌ منتهية (لم تُنظَّف بعد) تُعامَل كمجهول — كي لا يختلف هذا
            # المسار عن get_client_session في معنى «جلسةٍ صالحة».
            if session:
                try:
                    from db.security import session_is_expired
                    if session_is_expired(session):
                        session = None
                except Exception:
                    pass

        if session and session.get("client_id"):
            allowed = (rate_limit.check(f"s:{token}", rate_limit.WRITE_LIMIT)
                       and rate_limit.check(f"t:{session['client_id']}",
                                            rate_limit.TENANT_LIMIT))
        else:
            allowed = rate_limit.check(f"ip:{client_ip(request)}",
                                       rate_limit.ANON_LIMIT)

        if not allowed:
            return JSONResponse(
                {"detail": "طلبات كثيرة — تجاوزت حدَّ المعدّل، أعد المحاولة بعد قليل"},
                status_code=429,
            )
    return await call_next(request)


# طلبات الكتابة المُصادَقة بالكوكي معرّضة لتزوير الطلب عبر المواقع (CSRF).
# `samesite=lax` على كل كوكي هو الدفاع الأول؛ هذا فحص Origin/Referer دفاعٌ
# ثانٍ يرفض أي طلب كتابةٍ يحمل كوكي جلسة وأصلُه ليس من نطاقات ضيوف المعروفة.
from urllib.parse import urlsplit as _urlsplit  # noqa: E402

_CSRF_AUTH_COOKIES = ("client_token", "admin_token", "visitor_token")
# أسماء المضيفات لا تُميّز حالة الأحرف (RFC 3986) — تُخزَّن وتُقارَن صغيرةً.
_CSRF_ALLOWED_HOSTS = frozenset(
    _urlsplit(o).netloc.lower() for o in _ALLOWED_ORIGINS if _urlsplit(o).netloc
)


def _same_host(request: Request) -> str:
    """مضيف الطلب من ترويسة Host الخام (صغيرة).

    لا نستعمل X-Forwarded-Host هنا: إنه رأسٌ يحدّده العميل، ولا يصلح أساساً
    لقرار «سماح» أمني ما لم يضمن الوسيط تنظيفه. وHost يكفي ضد CSRF المتصفّح:
    في الطلب المزوّر عبر موقعٍ آخر يضبط المتصفّح Host على خادمنا (الهدف) لا
    على موقع المهاجم، بينما Origin يحمل موقعه — فيقع عدم التطابق فيُرفض. أي
    أصلٍ أول طرفٍ آخر (مضيفٌ عام مختلف) يجب إدراجه في `CORS_ORIGINS`.
    """
    return (request.headers.get("host") or "").lower()


@app.middleware("http")
async def csrf_origin_guard(request: Request, call_next):
    """دفاعٌ ثانٍ ضد CSRF: يتحقّق أن أصل طلب الكتابة المُصادَق بالكوكي موثوق.

    يُفحَص فقط حين يحمل الطلب كوكي جلسة (client/admin/visitor) ومنهجه مُغيِّر
    للحالة على `/api/*`. غياب Origin وReferer معاً يعني عميلاً غير متصفّح
    (تطبيق/أداة) فلا يُطبَّق — المتصفّحات تُرسل Origin على طلبات الكتابة عبر
    المواقع دائماً، وهي وحدها سطح خطر CSRF. الطلب من نفس المضيف يمرّ دائماً.
    """
    if (request.method in ("POST", "PUT", "PATCH", "DELETE")
            and request.url.path.startswith("/api/")
            and any(c in request.cookies for c in _CSRF_AUTH_COOKIES)):
        src = request.headers.get("origin") or request.headers.get("referer")
        if src:
            host = _urlsplit(src).netloc.lower()
            if host != _same_host(request) and host not in _CSRF_ALLOWED_HOSTS:
                return JSONResponse(
                    {"detail": "طلبٌ مرفوض — أصلٌ غير موثوق"}, status_code=403)
    return await call_next(request)


# ── الضغط يُسجَّل **بعد** بقيّة الوسطاء عمداً ─────────────────
#
# Starlette يجعل آخر وسيطٍ يُسجَّل هو الأبعد عن التطبيق. فلو سُجّل الضغط
# أولاً لصار ختمُ البصمة يعمل بعده، فيرى جسماً مضغوطاً لا نصّاً — وقد
# وقع هذا فعلاً: كل صفحة خرجت **فارغة** لكل متصفّح يطلب gzip، بينما
# curl (الذي لا يطلبه افتراضياً) يراها سليمة.
#
# بهذا الترتيب: يُختَم النصّ أولاً، ثم يُضغط المختوم.
app.add_middleware(GZipMiddleware, minimum_size=1000)

# ──────────────────────────────────────────────────────────────
#  Auth helpers
# ──────────────────────────────────────────────────────────────
def _get_admin_token(request: Request) -> Optional[str]:
    return request.cookies.get("admin_token")


def _get_client_token(request: Request) -> Optional[str]:
    return request.cookies.get("client_token")


def require_admin(request: Request):
    token = _get_admin_token(request)
    with _lock:
        session = _admin_sessions.get(token) if token else None
    if not session:
        raise HTTPException(status_code=401, detail="غير مصرح")
    # H3 fix: فرض انتهاء صلاحية جلسة المدير على الخادم (8 ساعات)
    try:
        from db.security import session_is_expired
        if session_is_expired(session):
            with _lock:
                _admin_sessions.pop(token, None)
            raise HTTPException(status_code=401, detail="انتهت صلاحية الجلسة")
    except HTTPException:
        raise
    except Exception:
        pass
    return session


def _session_from_row(row: dict) -> dict:
    """
    يبني جلسةً من صفّ client_sessions.

    غياب الدور يعني صفّاً كُتب قبل إضافة أعمدة الهوية — وتلك جلسات
    مالكٍ حصراً، إذ لم تكن هناك جلسات موظفين آنذاك. يُفترض `owner`
    لتلك وحدها، ولا يُفترض شيء لصفّ يحمل دوراً.
    """
    import json as _json

    role = row.get("role") or "owner"
    raw = row.get("permissions")
    permissions: list = []
    if raw:
        try:
            parsed = _json.loads(raw)
            # `json.loads("null")` يُعيد None لا قائمة، و`"*" in None`
            # يرمي TypeError داخل فحص الصلاحيات — أي عطل خادم بدل رفض.
            # يُقبل ما كان قائمةً فقط.
            if isinstance(parsed, list):
                permissions = [p for p in parsed if isinstance(p, str)]
        except (ValueError, TypeError):
            permissions = []
    elif role in ("owner", "gm"):
        permissions = ["*"]

    session = {
        "client_id": row["client_id"],
        "created_at": str(row.get("created_at") or ""),
        "role": role,
        "permissions": permissions,
    }
    for key in ("staff_id", "username", "full_name"):
        if row.get(key) is not None:
            session[key] = row[key]
    return session


def get_client_session(request: Request) -> Optional[dict]:
    token = _get_client_token(request)
    if not token:
        return None
    with _lock:
        session = _client_sessions.get(token)
    # If not in memory (e.g. after restart), try PostgreSQL
    if session is None:
        try:
            db = getattr(request.app.state, "db", None)
            if db and db.use_postgres:
                row = db.execute(
                    """SELECT client_id, created_at, role, staff_id,
                              username, full_name, permissions
                       FROM client_sessions
                       WHERE token=%s AND expires_at > NOW()""",
                    (token,), fetch="one"
                )
                if row:
                    # الهوية تُقرأ كما حُفظت.
                    # كانت تُبنى بـ role="owner" و["*"] مهما كان صاحبها،
                    # فأيّ جلسة تُستعاد بعد إعادة تشغيل تصير جلسةَ مالك —
                    # تصعيدُ صلاحيات كامل لكل موظف.
                    session = _session_from_row(dict(row))
                    with _lock:
                        _client_sessions[token] = session
        except Exception:
            pass
    if session is None:
        return None
    # Finding #8: enforce server-side session TTL (8 hours)
    try:
        from db.security import session_is_expired, is_token_revoked
    except Exception:
        return session  # security module unavailable — keep prior behavior
    # M5 fix: فشل-مغلق — أي خطأ في فحص الصلاحية/الإبطال يُبطل الجلسة بدل قبولها
    try:
        if session_is_expired(session):
            with _lock:
                _client_sessions.pop(token, None)
            return None
        db = getattr(request.app.state, "db", None)
        if db and is_token_revoked(db, token):
            with _lock:
                _client_sessions.pop(token, None)
            return None
    except Exception:
        log.warning("session check failed — rejecting session (fail-closed)")
        return None
    return session


def require_client(request: Request) -> dict:
    session = get_client_session(request)
    if not session:
        raise HTTPException(status_code=401, detail="غير مصرح")
    # Finding #3: enforce non-empty client_id
    if not session.get("client_id", "").strip():
        raise HTTPException(status_code=401, detail="جلسة غير صالحة — client_id مفقود")
    return session


# ──────────────────────────────────────────────────────────────
#  HTML Helpers
# ──────────────────────────────────────────────────────────────

from html_pages import _login_page, _admin_login_page, _admin_dashboard, _client_dashboard  # noqa: E402, F401


# ──────────────────────────────────────────────────────────────
#  تسجيل وحدات المسارات — سجلٌّ واحد لكل الوحدات
#  يُنفَّذ في آخر الملف ليكون كل ما تحتاجه الوحدات معرَّفاً
#  الترتيب لا يؤثر — كل وحدة تحمل بادئتها في APIRouter(prefix=…)
#  فشل وحدة لا يُسقط التطبيق، ويظهر في ملخّص الإقلاع أدناه.
# ──────────────────────────────────────────────────────────────
ROUTE_MODULES: list[tuple[str, str]] = [
    ("frontdesk",    "الاستقبال"),
    ("bookings",     "الحجوزات"),
    ("housekeeping", "التدبير الفندقي"),
    ("maintenance",  "الصيانة"),
    ("inventory",    "المخزون"),
    ("warehouses",   "المستودعات"),
    ("pos",          "نقاط البيع"),
    ("accounting",   "المحاسبة"),
    ("hr",           "الموارد البشرية"),
    ("crm",          "علاقات العملاء"),
    ("kpi",          "مؤشرات الأداء"),
    ("analytics",    "التحليلات عبر الوحدات"),
    ("reviews",      "التقييمات"),
    ("night_audit",  "تدقيق الليل"),
    ("zatca",        "الفوترة الإلكترونية"),
    ("tourism",      "الرحلات السياحية"),
    ("destinations", "الوجهات السياحية"),
    ("channels",     "قنوات التوزيع"),
    ("pricing",      "التسعير الديناميكي"),
    ("integration",  "التنسيق عبر الوحدات"),
    ("open_api",     "الـ Open API"),
    # وحدات كانت معرَّفة على app مباشرةً قبل التقسيم
    ("pages",        "الصفحات العامة و PWA و SEO"),
    ("system",       "الصحة والحالة والنسخ الاحتياطي"),
    ("admin",        "لوحة مالك المنصة"),
    ("leads",        "الزوّار المهتمّون"),
    ("visitors",     "بوابة الزوّار — حجزٌ لأنفسهم"),
    ("listings",     "العرض — تُخصّصه المنشأة"),
    ("search",       "البحث — يتصفّحه الزائر"),
    ("auth",         "دخول المنشأة وتسجيلها"),
    ("hotel_ops",    "العمليات الفندقية"),
    ("staff_accounts", "حسابات دخول الموظفين"),
    ("booking_services", "الإفطار والتوصيل"),
    ("smart_alerts",     "إنذارات المفتاح الذكي"),
    ("insights",     "المؤشرات والتحليلات"),
    ("commerce",     "الباقات والدفع والتذاكر"),
    ("i18n",         "تعدّد اللغة — حزمة النصوص"),
    ("subscription", "الاشتراك — الحالة والتنبيه ورسالة الدفع"),
    ("moyasar_webhook", "ميسر — ويب هوك الدفع (توقيع · إيديمبوتنسي · سجلّ)"),
    ("billing", "بوابة الفوترة — الحالة · الفواتير · بدء الدفع"),
    ("integrations", "اعتمادات التكاملات — لكل مشترك، مشفّرة تحت تصرّفه"),
]


def _register_route_modules() -> None:
    """يستورد كل وحدة ويُركّبها، ويسجّل ملخّصاً بما نجح وما فشل."""
    import importlib

    loaded: list[str] = []
    failed: list[tuple[str, str]] = []

    for name, label in ROUTE_MODULES:
        try:
            module = importlib.import_module(f"routes.{name}")
            app.include_router(module.router)
            loaded.append(name)
        except Exception as exc:
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            log.warning("✗ تعذّر تحميل وحدة %s (%s) — %s", name, label, exc)

    log.info("✓ وحدات المسارات: %d/%d محمَّلة", len(loaded), len(ROUTE_MODULES))
    if failed:
        log.error("✗ وحدات فاشلة (%d): %s", len(failed), ", ".join(n for n, _ in failed))


_register_route_modules()
