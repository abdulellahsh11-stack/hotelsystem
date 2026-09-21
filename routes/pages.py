#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/pages.py — الصفحات العامة و PWA والاختصارات و SEO
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import os
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import (
    HTMLResponse, PlainTextResponse, RedirectResponse, Response,
)

from app_core import (
    _lock, _admin_sessions, get_client_session, _get_admin_token,
)
from html_pages import (
    _login_page, _admin_login_page, _admin_dashboard, _client_dashboard,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Public routes
# ──────────────────────────────────────────────────────────────
_MARKETING_PAGE = os.path.join("static", "dheuof", "website", "index.html")
_APP_LAUNCHER = os.path.join("static", "dheuof", "index.html")


def _serve(path: str) -> Optional[HTMLResponse]:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return None


def _ga_snippet() -> str:
    """مقتطف Google Analytics — يُحقن فقط إن ضُبط GA_MEASUREMENT_ID، وإلا فراغ.
    لا يُكتب المعرّف في الكود؛ يأتي من البيئة."""
    gid = os.environ.get("GA_MEASUREMENT_ID", "").strip()
    if not gid:
        return ""
    # المعرّف مقيَّد بالنمط G-XXXX فلا يُحقن نصٌّ عشوائي
    import re as _re
    if not _re.fullmatch(r"G-[A-Z0-9]{4,20}", gid):
        return ""
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>\n'
        '<script>window.dataLayer=window.dataLayer||[];'
        'function gtag(){dataLayer.push(arguments);}gtag("js",new Date());'
        f'gtag("config","{gid}");</script>'
    )


def _serve_marketing() -> Optional[HTMLResponse]:
    """الموقع التسويقي مع حقن مقتطف التحليلات مكان العلامة عند الحاجة."""
    if not os.path.exists(_MARKETING_PAGE):
        return None
    with open(_MARKETING_PAGE, encoding="utf-8") as f:
        html = f.read()
    html = html.replace("<!--#GA_SNIPPET#-->", _ga_snippet())
    return HTMLResponse(html)


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    # الزائر غير المسجَّل يرى الموقع التسويقي؛ العميل المسجَّل يذهب للوحة البرامج
    if get_client_session(request) is None:
        page = _serve_marketing()
        if page is not None:
            return page
    return _serve(_APP_LAUNCHER) or HTMLResponse(_login_page())


@router.get("/app", response_class=HTMLResponse)
async def dheuof_app(request: Request):
    # لوحة البرامج دائماً — بغضّ النظر عن حالة الجلسة
    return _serve(_APP_LAUNCHER) or HTMLResponse(_login_page())


# ──────────────────────────────────────────────────────────────
#  PWA — installable on iOS / Android / Browser (root scope)
# ──────────────────────────────────────────────────────────────
@router.get("/manifest.json")
async def pwa_manifest():
    path = os.path.join("static", "dheuof", "manifest.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/manifest+json")
    return Response(status_code=404)


@router.get("/sw.js")
async def pwa_service_worker():
    path = os.path.join("static", "dheuof", "sw.js")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            # Service-Worker-Allowed lets the worker control the whole site (root scope)
            return Response(
                content=f.read(),
                media_type="application/javascript",
                headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
            )
    return Response(status_code=404)


@router.get("/marketing", response_class=HTMLResponse)
async def marketing_page(request: Request):
    # نفس صفحة "/" التسويقية — محفوظ للتوافق مع الروابط القديمة.
    # الـ canonical داخل الصفحة يشير إلى "/" فلا يقع تكرار محتوى.
    return _serve_marketing() or HTMLResponse(_login_page())


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    # Already authenticated → go straight to the app
    if get_client_session(request) is not None:
        return RedirectResponse("/", status_code=302)
    ref = request.query_params.get("ref", "")
    return HTMLResponse(_login_page(ref_code=ref))


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    token = _get_admin_token(request)
    with _lock:
        is_auth = token and token in _admin_sessions
    if not is_auth:
        return HTMLResponse(_admin_login_page())

    return HTMLResponse(_admin_dashboard([], {}))


@router.get("/guests", response_class=HTMLResponse)
async def guests_page(request: Request):
    session = get_client_session(request)
    if not session:
        return RedirectResponse("/login")
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {"id": session["client_id"]}
    return HTMLResponse(_client_dashboard(client))


@router.get("/bookings", response_class=HTMLResponse)
async def bookings_page(request: Request):
    session = get_client_session(request)
    if not session:
        return RedirectResponse("/login")
    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {"id": session["client_id"]}
    return HTMLResponse(_client_dashboard(client))


# ──────────────────────────────────────────────────────────────
#  Module shortcut routes — dheuof.com/hr, /accounting, etc.
# ──────────────────────────────────────────────────────────────
def _serve_module(path: str) -> HTMLResponse:
    full = os.path.join("static", "dheuof", "modules", path, "index.html")
    if os.path.exists(full):
        with open(full, encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return RedirectResponse("/")

@router.get("/static/dheuof/modules/01-guests/checkin.html")
async def redirect_checkin():
    return RedirectResponse("/static/dheuof/modules/01-guests/index.html", status_code=301)

@router.get("/dheuof",   response_class=HTMLResponse)
@router.get("/guests-module", response_class=HTMLResponse)
async def mod_guests():    return _serve_module("01-guests")

@router.get("/shumus",   response_class=HTMLResponse)
async def mod_shumus():    return _serve_module("02-shumus")

@router.get("/tourism",  response_class=HTMLResponse)
async def mod_tourism():   return _serve_module("03-tourism")

@router.get("/inventory",response_class=HTMLResponse)
async def mod_inv():       return _serve_module("04-inventory")

@router.get("/warehouse",response_class=HTMLResponse)
async def mod_wh():        return _serve_module("05-warehouse")

@router.get("/account",  response_class=HTMLResponse)
@router.get("/accounting",response_class=HTMLResponse)
async def mod_acc():       return _serve_module("06-accounting")

@router.get("/pos",      response_class=HTMLResponse)
async def mod_pos():       return _serve_module("07-pos")

@router.get("/key",      response_class=HTMLResponse)
@router.get("/smart-key",response_class=HTMLResponse)
async def mod_key():       return _serve_module("08-smart-key")

@router.get("/hr",       response_class=HTMLResponse)
async def mod_hr():        return _serve_module("09-hr")

@router.get("/channels", response_class=HTMLResponse)
@router.get("/marketing-channels", response_class=HTMLResponse)
async def mod_ch():        return _serve_module("10-channel-marketing")

@router.get("/analytics",response_class=HTMLResponse)
async def mod_an():        return _serve_module("12-analytics")

@router.get("/staff",    response_class=HTMLResponse)
async def mod_st():        return _serve_module("13-staff-tracker")

@router.get("/goals",    response_class=HTMLResponse)
async def mod_go():        return _serve_module("14-manager-goals")

@router.get("/ota-bookings",   response_class=HTMLResponse)
async def mod_bookings():  return _serve_module("17-bookings")

@router.get("/trips",          response_class=HTMLResponse)
@router.get("/tourism-trips",  response_class=HTMLResponse)
async def mod_trips():     return _serve_module("15-tourism-trips")


# ──────────────────────────────────────────────────────────────
#  Dashboard Page — لوحة التحكم الكاملة
# ──────────────────────────────────────────────────────────────
@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    session = get_client_session(request)
    if not session:
        return RedirectResponse("/login")
    import os
    dash_path = os.path.join("static", "dashboard.html")
    if os.path.exists(dash_path):
        with open(dash_path, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return RedirectResponse("/")


# ──────────────────────────────────────────────────────────────
#  SEO Routes
# ──────────────────────────────────────────────────────────────
@router.get("/robots.txt")
async def robots_txt():
    return PlainTextResponse(
        "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/\n"
        "Sitemap: https://dheuof.com/sitemap.xml\n"
    )


# المسارات المُدرجة في sitemap — تطابق وسوم canonical في ملفات static
_SITEMAP_URLS = [
    # "/" هو الموقع التسويقي للزائر — و"/marketing" مستبعد لأنه نفس الصفحة
    # ويحمل canonical يشير إلى "/"، فإدراجه يرسل إشارة محتوى مكرر.
    ("/",            "weekly",  "1.0"),
    ("/dheuof",      "weekly",  "0.8"),
    ("/ota-bookings", "weekly", "0.8"),
    ("/accounting",  "weekly",  "0.8"),
    ("/pos",         "weekly",  "0.7"),
    ("/channels",    "weekly",  "0.7"),
    ("/analytics",   "monthly", "0.7"),
    ("/inventory",   "monthly", "0.6"),
    ("/warehouse",   "monthly", "0.6"),
    ("/hr",          "monthly", "0.6"),
    ("/shumus",      "monthly", "0.6"),
    ("/tourism",     "monthly", "0.6"),
    ("/trips",       "monthly", "0.6"),
    ("/smart-key",   "monthly", "0.6"),
    ("/staff",       "monthly", "0.5"),
    ("/goals",       "monthly", "0.5"),
    ("/static/dheuof/packages.html",   "monthly", "0.8"),
    ("/static/dheuof/onboarding.html", "monthly", "0.7"),
    ("/static/dheuof/api-docs.html",   "monthly", "0.6"),
    ("/privacy",  "yearly", "0.3"),
    ("/terms",    "yearly", "0.3"),
]


@router.get("/sitemap.xml")
async def sitemap():
    from fastapi.responses import Response
    entries = "\n".join(
        f"  <url><loc>https://dheuof.com{path}</loc>"
        f"<changefreq>{freq}</changefreq><priority>{prio}</priority></url>"
        for path, freq, prio in _SITEMAP_URLS
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{entries}\n</urlset>")
    return Response(content=xml, media_type="application/xml")


@router.get("/ref/{code}", response_class=HTMLResponse)
async def referral_redirect(code: str):
    """رابط الإحالة — يفتح صفحة التسجيل مع كود المسوق محمّل تلقائياً"""
    return HTMLResponse(_login_page(ref_code=code.upper()))


# ──────────────────────────────────────────────────────────────
#  أصول الجذر: أيقونة الموقع وصورة المعاينة الاجتماعية
# ──────────────────────────────────────────────────────────────
def _serve_file(path: str, media_type: str) -> Response:
    if os.path.exists(path):
        with open(path, "rb") as f:
            return Response(content=f.read(), media_type=media_type,
                            headers={"Cache-Control": "public, max-age=86400"})
    return Response(status_code=404)


@router.get("/favicon.svg")
async def favicon_svg():
    return _serve_file(os.path.join("static", "favicon.svg"), "image/svg+xml")


@router.get("/favicon.ico")
async def favicon_ico():
    # لا ملفّ ico ثنائي — نوجّه إلى نسخة SVG المتّجهة (يدعمها المتصفّح الحديث)
    return RedirectResponse("/favicon.svg", status_code=301)


@router.get("/og-image.png")
async def og_image():
    return _serve_file(os.path.join("static", "og-image.png"), "image/png")


# ──────────────────────────────────────────────────────────────
#  الصفحات القانونية (هيكلٌ الآن — النصّ يُضاف لاحقاً)
# ──────────────────────────────────────────────────────────────
@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page():
    return _serve(os.path.join("static", "dheuof", "website", "privacy.html")) \
        or HTMLResponse("<h1>سياسة الخصوصية</h1>", status_code=200)


@router.get("/terms", response_class=HTMLResponse)
async def terms_page():
    return _serve(os.path.join("static", "dheuof", "website", "terms.html")) \
        or HTMLResponse("<h1>الشروط والأحكام</h1>", status_code=200)


