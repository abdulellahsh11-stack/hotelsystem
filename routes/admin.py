#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/admin.py — لوحة مالك المنصة — الدخول والإحصاءات والعملاء والمسوقون
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (
    HTMLResponse, JSONResponse, RedirectResponse,
)

from app_core import (
    log, _lock, _admin_sessions, _client_sessions,
    _COOKIE_SECURE, _new_token, _make_password, _hash_password,
    require_admin,
    _get_admin_token,
)
from db.store import public_client, public_settings
from html_pages import (
    _admin_login_page,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Admin Auth
# ──────────────────────────────────────────────────────────────
@router.post("/api/admin/login")
async def admin_login(request: Request):
    form = await request.form()
    password = form.get("password", "")
    cfg = request.app.state.cfg

    h = _hash_password(str(password), cfg.pass_salt)
    # compare_digest لا «!=»: المقارنة العادية تنتهي عند أول اختلاف،
    # فيتسرّب من زمنها ما يُستدلّ به على التجزئة. وهذه كلمة مرور مالك
    # المنصة كلها.
    if not secrets.compare_digest(h, str(cfg.admin_pass_hash or "")):
        if request.headers.get("content-type", "").startswith("application/json"):
            return JSONResponse({"success": False, "error": "كلمة المرور خاطئة"}, status_code=401)
        return HTMLResponse(_admin_login_page("كلمة المرور خاطئة"), status_code=401)

    token = _new_token()
    with _lock:
        _admin_sessions[token] = {"created_at": datetime.now().isoformat()}

    response = RedirectResponse("/admin", status_code=303)
    response.set_cookie("admin_token", token, httponly=True, samesite="lax", secure=_COOKIE_SECURE, max_age=86400)
    return response


@router.get("/api/admin/logout")
async def admin_logout(request: Request):
    # H3 fix: أبطل الرمز فعلياً على الخادم لا الكوكي فقط
    token = _get_admin_token(request)
    with _lock:
        _admin_sessions.pop(token, None)
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie("admin_token")
    return response


@router.post("/api/admin/logout")
async def admin_logout_post(request: Request):
    token = _get_admin_token(request)
    with _lock:
        _admin_sessions.pop(token, None)
    response = JSONResponse({"success": True})
    response.delete_cookie("admin_token")
    return response


# ──────────────────────────────────────────────────────────────
#  Admin — Stats & Clients
# ──────────────────────────────────────────────────────────────
@router.get("/api/admin/clients")
async def admin_clients(request: Request, _=Depends(require_admin)):
    cfg = request.app.state.cfg
    store = request.app.state.store
    clients = store.get_all_clients()
    owner_id = getattr(cfg, "owner_client_id", "") or ""
    clients = [public_client(c) for c in clients]
    for c in clients:
        c.setdefault("sub_end", c.get("subscription_expires", c.get("trial_end", "")))
        c.setdefault("sub_start", "")
        c.setdefault("sub_price", 0)
        c["is_owner"] = (str(c.get("id", "")) == owner_id)
    return {"success": True, "clients": clients}


@router.post("/api/admin/clients")
async def admin_create_client(request: Request, _=Depends(require_admin)):
    data = await request.json()
    client_id = str(data.get("id", "")).strip()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", "")).strip()
    plan = str(data.get("plan", "starter")).strip()
    email = str(data.get("email", "")).strip()

    if not all([client_id, name, password]):
        return JSONResponse({"success": False, "error": "id و name و password مطلوبة"}, status_code=400)

    store = request.app.state.store

    existing = store.get_client(client_id)
    if existing:
        return JSONResponse({"success": False, "error": "المعرف مستخدم بالفعل"}, status_code=400)

    pass_hash, pass_salt = _make_password(password)
    sub_end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    client = {
        "id": client_id,
        "name": name,
        "hotel_name": name,
        "email": email,
        "plan": plan,
        "status": "trial",
        "pass_hash": pass_hash,
        "pass_salt": pass_salt,
        "sub_end": sub_end,
        "sub_start": datetime.now().strftime("%Y-%m-%d"),
        "sub_price": 0,
        "created_at": datetime.now().isoformat(),
        "settings": {},
    }
    store.save_client(client)
    return JSONResponse({"success": True, "client": public_client(client)})


@router.post("/api/admin/owner-setup")
async def admin_owner_setup(request: Request, _=Depends(require_admin)):
    """إنشاء أو تحديث حساب المالك — enterprise مدى الحياة"""
    data = await request.json()
    client_id = str(data.get("client_id", "")).strip()
    name = str(data.get("name", "")).strip()
    password = str(data.get("password", "")).strip()
    email = str(data.get("email", "")).strip()

    if not all([client_id, name, password]):
        return JSONResponse({"success": False, "error": "client_id و name و password مطلوبة"}, status_code=400)

    cfg = request.app.state.cfg
    store = request.app.state.store

    pass_hash, pass_salt = _make_password(password)
    sub_end = (datetime.now() + timedelta(days=36500)).strftime("%Y-%m-%d")  # 100 years
    client = store.get_client(client_id) or {}
    client.update({
        "id": client_id,
        "name": name,
        "hotel_name": name,
        "email": email,
        "plan": "enterprise",
        "status": "active",
        "pass_hash": pass_hash,
        "pass_salt": pass_salt,
        "sub_end": sub_end,
        "sub_start": datetime.now().strftime("%Y-%m-%d"),
        "sub_price": 0,
        "is_owner_account": True,
        "settings": public_settings(client),
        "created_at": client.get("created_at", datetime.now().isoformat()),
    })
    store.save_client(client)

    # persist owner_client_id to cfg so the flag shows up immediately
    cfg.owner_client_id = client_id
    log.info(f"Owner account set: {client_id} ({email})")
    return JSONResponse({"success": True, "client_id": client_id, "sub_end": sub_end})


@router.get("/api/admin/clients/{client_id}")
async def admin_get_client(client_id: str, request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    return {"success": True, "client": public_client(client)}


@router.put("/api/admin/clients/{client_id}")
async def admin_update_client(client_id: str, request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    data = await request.json()
    for k in ["name", "hotel_name", "plan", "status", "subscription_expires", "settings"]:
        if k in data:
            client[k] = data[k]
    if "password" in data and data["password"]:
        # يجب أن يُكتب الملح مع التجزئة معاً.
        # كان يُكتب pass_hash بالملح العام بينما pass_salt القديم باقٍ،
        # و_verify_password يتحقق بملح الحساب — فلا تُطابق التجزئةُ أبداً
        # وتُقفَل المنشأة نهائياً بلا وسيلة استرداد.
        client["pass_hash"], client["pass_salt"] = _make_password(str(data["password"]))
    store.save_client(client)
    return {"success": True, "client": public_client(client)}


@router.delete("/api/admin/clients/{client_id}")
async def admin_delete_client(client_id: str, request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    store.delete_client(client_id)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Admin extended endpoints
# ──────────────────────────────────────────────────────────────
@router.post("/api/admin/clients/{client_id}/toggle")
async def admin_toggle_client(client_id: str, request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    client = store.get_client(client_id)
    if client:
        client["status"] = "suspended" if client.get("status") == "active" else "active"
        store.save_client(client)
    return {"success": True}


# ── مفاتيح API لكل منشأة — يخصّصها مالك المنصّة ──────────────────
# رقم المنشأة (client_id) مسجَّلٌ في قاعدة البيانات عند إنشائها، وكل
# مفتاحٍ يُصدَر هنا مرتبطٌ به في جدول api_keys (تجزئة SHA-256 لا الخام).
# مالك المنصّة وحده يُصدر أو يُبطل — عبر require_admin.
def _keymgr(request: Request):
    mgr = getattr(request.app.state, "api_keys", None)
    if mgr is None:
        raise HTTPException(status_code=503,
                            detail="مدير المفاتيح غير مهيّأ (تحتاج PostgreSQL)")
    return mgr


def _client_or_404(request: Request, client_id: str) -> dict:
    client = request.app.state.store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    return client


@router.get("/api/admin/clients/{client_id}/api-keys")
async def admin_list_api_keys(client_id: str, request: Request, _=Depends(require_admin)):
    """مفاتيح API الخاصة بمنشأةٍ بعينها (بالقناع لا الخام)."""
    _client_or_404(request, client_id)
    mgr = _keymgr(request)
    return {"success": True, "keys": mgr.list_keys(client_id),
            "scopes": mgr.available_scopes()}


@router.post("/api/admin/clients/{client_id}/api-keys")
async def admin_issue_api_key(client_id: str, request: Request, _=Depends(require_admin)):
    """يُصدر مفتاحاً جديداً للمنشأة ويُعيد الخام مرّةً واحدة فقط."""
    _client_or_404(request, client_id)
    mgr = _keymgr(request)
    body = await request.json()
    name = str(body.get("name") or "").strip()[:120]
    scopes = body.get("scopes") or None
    if scopes is not None:
        allowed = set(mgr.available_scopes())
        scopes = [s for s in scopes if s in allowed]
    issued = mgr.issue_key(client_id, name=name, scopes=scopes)
    return {"success": True, "issued": issued}


@router.post("/api/admin/clients/{client_id}/api-keys/{key_id}/revoke")
async def admin_revoke_api_key(client_id: str, key_id: int, request: Request,
                               _=Depends(require_admin)):
    """يُبطل مفتاحاً للمنشأة (لا يُحذف — يبقى للتدقيق، غير فعّال)."""
    _client_or_404(request, client_id)
    mgr = _keymgr(request)
    ok = mgr.revoke_key(client_id, key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="المفتاح غير موجود لهذه المنشأة")
    return {"success": True}


@router.get("/api/admin/keys")
async def admin_get_keys(request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "keys": data.get("activation_keys", [])}


@router.post("/api/admin/keys/generate")
async def admin_gen_key(request: Request, _=Depends(require_admin)):
    body = await request.json()
    plan = body.get("plan", "trial")
    days = int(body.get("days", 30))
    key = "-".join([secrets.token_hex(4).upper() for _ in range(4)])
    entry = {"key": key, "plan": plan, "days": days, "used": False, "created_at": datetime.now().isoformat()}
    store = request.app.state.store
    data = store.get_admin_data()
    data.setdefault("activation_keys", []).append(entry)
    store.save_admin_data(data)
    return {"success": True, "key": key}


@router.post("/api/admin/keys/revoke")
async def admin_revoke_key(request: Request, _=Depends(require_admin)):
    body = await request.json()
    key = body.get("key", "")
    store = request.app.state.store
    data = store.get_admin_data()
    data["activation_keys"] = [k for k in data.get("activation_keys", []) if k.get("key") != key]
    store.save_admin_data(data)
    return {"success": True}


@router.get("/api/admin/payments")
async def admin_get_payments(request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "payments": data.get("payments", [])}


@router.post("/api/admin/payments/add")
async def admin_add_payment(request: Request, _=Depends(require_admin)):
    body = await request.json()
    payment = {"id": secrets.token_hex(8), "client_id": body.get("client_id", ""), "amount": float(body.get("amount", 0)), "plan": body.get("plan", ""), "date": datetime.now().isoformat()}
    store = request.app.state.store
    data = store.get_admin_data()
    data.setdefault("payments", []).append(payment)
    store.save_admin_data(data)
    return {"success": True, "payment": payment}


@router.get("/api/admin/tickets")
async def admin_get_tickets(request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "tickets": data.get("tickets", [])}


@router.post("/api/admin/tickets/reply")
async def admin_reply_ticket(request: Request, _=Depends(require_admin)):
    body = await request.json()
    tid = str(body.get("id", ""))
    reply = body.get("reply", "")
    store = request.app.state.store
    data = store.get_admin_data()
    for t in data.get("tickets", []):
        if str(t.get("id")) == tid:
            t.setdefault("replies", []).append({"text": reply, "from": "admin", "at": datetime.now().isoformat()})
            break
    store.save_admin_data(data)
    return {"success": True}


@router.post("/api/admin/tickets/close")
async def admin_close_ticket(request: Request, _=Depends(require_admin)):
    body = await request.json()
    tid = str(body.get("id", ""))
    store = request.app.state.store
    data = store.get_admin_data()
    for t in data.get("tickets", []):
        if str(t.get("id")) == tid:
            t["status"] = "closed"
            break
    store.save_admin_data(data)
    return {"success": True}


@router.get("/api/admin/sessions")
async def admin_list_sessions(request: Request, _=Depends(require_admin)):
    """قائمة الجلسات النشطة لجميع المنشآت"""
    store = request.app.state.store
    with _lock:
        raw = dict(_client_sessions)
    result = []
    for token, sess in raw.items():
        cid = sess.get("client_id", "")
        client = store.get_client(cid) or {}
        result.append({
            "token_prefix": token[:8],
            "client_id": cid,
            "client_name": client.get("name", client.get("hotel_name", cid)),
            "plan": client.get("plan", "trial"),
            "created_at": sess.get("created_at", ""),
        })
    result.sort(key=lambda x: x["created_at"], reverse=True)
    return {"success": True, "sessions": result}


@router.post("/api/admin/sessions/{token_prefix}/revoke")
async def admin_revoke_session(token_prefix: str, request: Request, _=Depends(require_admin)):
    """إنهاء جلسة نشطة بواسطة المدير"""
    with _lock:
        to_remove = [t for t in _client_sessions if t.startswith(token_prefix)]
        for t in to_remove:
            _client_sessions.pop(t, None)
    return {"success": True, "revoked": len(to_remove)}


@router.get("/api/admin/subscriptions")
async def admin_list_subscriptions(request: Request, _=Depends(require_admin)):
    """قائمة اشتراكات جميع المنشآت"""
    cfg = request.app.state.cfg
    store = request.app.state.store
    clients = store.get_all_clients()
    owner_id = getattr(cfg, "owner_client_id", "") or ""
    subs = []
    for c in clients:
        subs.append({
            "client_id": c.get("id", ""),
            "name": c.get("name", c.get("hotel_name", c.get("id", ""))),
            "plan": c.get("plan", "trial"),
            "status": c.get("status", "trial"),
            "sub_start": c.get("sub_start", ""),
            "sub_end": c.get("sub_end", c.get("subscription_expires", c.get("trial_end", ""))),
            "price": c.get("sub_price", 0),
            "is_owner": (str(c.get("id", "")) == owner_id),
        })
    subs.sort(key=lambda x: (0 if x.get("is_owner") else 1, x.get("sub_end") or ""))
    return {"success": True, "subscriptions": subs}


@router.put("/api/admin/subscriptions/{client_id}")
async def admin_update_subscription(client_id: str, request: Request, _=Depends(require_admin)):
    """تحديث اشتراك منشأة"""
    store = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    body = await request.json()
    for field in ["plan", "status", "sub_start", "sub_end", "sub_price"]:
        if field in body:
            client[field] = body[field]
    # sync status on the client record as well
    if "status" in body:
        client["status"] = body["status"]
    store.save_client(client)
    return {"success": True, "client_id": client_id}


@router.post("/api/admin/clients/{client_id}/reset-password")
async def admin_reset_client_password(client_id: str, request: Request, _=Depends(require_admin)):
    """إعادة تعيين كلمة مرور مدير المنشأة"""
    store = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    body = await request.json()
    password = str(body.get("password", "")).strip()
    if len(password) < 4:
        return JSONResponse({"success": False, "error": "كلمة المرور قصيرة جداً"}, status_code=400)
    client["pass_hash"], client["pass_salt"] = _make_password(password)
    store.save_client(client)
    return {"success": True}


@router.put("/api/admin/clients/{client_id}/modules")
async def admin_update_modules(client_id: str, request: Request, _=Depends(require_admin)):
    """تحديث الوحدات المفعّلة لمنشأة"""
    store = request.app.state.store
    client = store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    body = await request.json()
    client["enabled_modules"] = body.get("enabled_modules", [])
    store.save_client(client)
    return {"success": True, "enabled_modules": client["enabled_modules"]}


@router.get("/api/admin/employees")
async def admin_list_employees(request: Request, client_id: Optional[str] = None, _=Depends(require_admin)):
    """قائمة الموظفين من قاعدة البيانات مع آخر نشاط"""
    db = request.app.state.db
    store = request.app.state.store
    if not db.use_postgres:
        return {"success": True, "employees": []}
    # نطاق مالك المنصة: هذه القائمة تعبر المنشآت بحكم وظيفتها، وRLS
    # تمنع ذلك على جلسة منشأة. يُفتح النطاق هنا وحده — بعد require_admin
    # — ويُغلق بانتهاء الكتلة ولو وقع استثناء.
    try:
        from db.tenant_context import platform_scope
    except Exception:
        from contextlib import nullcontext as platform_scope

    try:
      with platform_scope():
          if client_id:
              rows = db.execute("""
                  SELECT e.client_id, e.id,
                         COALESCE(e.full_name_ar, e.full_name_en, '') AS name,
                         COALESCE(e.position, '') AS role,
                         MAX(ra.created_at) as last_active,
                         COUNT(ra.id) as task_count
                  FROM employees e
                  LEFT JOIN room_actions ra ON ra.client_id=e.client_id AND ra.performed_by=COALESCE(e.full_name_ar, e.full_name_en)
                  WHERE e.client_id=%s
                  GROUP BY e.client_id, e.id, e.full_name_ar, e.full_name_en, e.position
                  ORDER BY last_active DESC NULLS LAST
              """, (client_id,), fetch="all")
          else:
              rows = db.execute("""
                  SELECT e.client_id, e.id,
                         COALESCE(e.full_name_ar, e.full_name_en, '') AS name,
                         COALESCE(e.position, '') AS role,
                         MAX(ra.created_at) as last_active,
                         COUNT(ra.id) as task_count
                  FROM employees e
                  LEFT JOIN room_actions ra ON ra.client_id=e.client_id AND ra.performed_by=COALESCE(e.full_name_ar, e.full_name_en)
                  GROUP BY e.client_id, e.id, e.full_name_ar, e.full_name_en, e.position
                  ORDER BY last_active DESC NULLS LAST
                  LIMIT 200
              """, fetch="all")
          clients_map = {c["id"]: c.get("name", c.get("hotel_name", c["id"])) for c in store.get_all_clients()}
          result = []
          for r in (rows or []):
              d = dict(r)
              d["client_name"] = clients_map.get(d.get("client_id", ""), d.get("client_id", ""))
              if d.get("last_active"):
                  d["last_active"] = str(d["last_active"])
              result.append(d)
          return {"success": True, "employees": result}
    except Exception as e:
        return {"success": True, "employees": [], "warning": str(e)}


@router.get("/api/admin/settings")
async def admin_get_settings(request: Request, _=Depends(require_admin)):
    store = request.app.state.store
    data = store.get_admin_data()
    return {"success": True, "settings": data.get("settings", {})}


@router.post("/api/admin/settings/save")
async def admin_save_settings(request: Request, _=Depends(require_admin)):
    body = await request.json()
    store = request.app.state.store
    data = store.get_admin_data()
    data.setdefault("settings", {}).update(body)
    store.save_admin_data(data)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Admin — Marketers (المسوقون)
# ──────────────────────────────────────────────────────────────
@router.get("/api/admin/marketers")
async def admin_list_marketers(request: Request, _=Depends(require_admin)):
    db = request.app.state.db
    if not db.use_postgres:
        return {"success": True, "marketers": []}
    try:
        rows = db.execute("""
            SELECT m.*,
                   COUNT(r.id) AS referral_count,
                   COALESCE(SUM(0), 0) AS total_earnings
            FROM marketers m
            LEFT JOIN marketer_referrals r ON r.marketer_id = m.id
            GROUP BY m.id
            ORDER BY referral_count DESC
        """, fetch="all")
        return {"success": True, "marketers": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "marketers": [], "warning": str(e)}


@router.post("/api/admin/marketers")
async def admin_create_marketer(request: Request, _=Depends(require_admin)):
    body = await request.json()
    name = str(body.get("name", "")).strip()
    if not name:
        return JSONResponse({"success": False, "error": "الاسم مطلوب"}, status_code=400)
    db = request.app.state.db
    # توليد كود فريد إذا لم يُحدَّد
    ref_code = str(body.get("ref_code", "")).strip().upper()
    if not ref_code:
        ref_code = secrets.token_hex(4).upper()
    try:
        row = db.execute("""
            INSERT INTO marketers (name, phone, email, ref_code, commission_rate, notes)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING *
        """, (name, body.get("phone",""), body.get("email",""),
              ref_code, float(body.get("commission_rate", 10)),
              body.get("notes","")), fetch="one")
        return {"success": True, "marketer": dict(row)}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.put("/api/admin/marketers/{mktr_id}")
async def admin_update_marketer(mktr_id: int, request: Request, _=Depends(require_admin)):
    body = await request.json()
    db = request.app.state.db
    fields = []
    vals = []
    for f in ["name", "phone", "email", "commission_rate", "status", "notes"]:
        if f in body:
            fields.append(f"{f}=%s")
            vals.append(body[f])
    if not fields:
        return {"success": True}
    vals.append(mktr_id)
    db.execute(f"UPDATE marketers SET {', '.join(fields)} WHERE id=%s", vals)
    return {"success": True}


@router.delete("/api/admin/marketers/{mktr_id}")
async def admin_delete_marketer(mktr_id: int, request: Request, _=Depends(require_admin)):
    db = request.app.state.db
    db.execute("UPDATE marketers SET status='inactive' WHERE id=%s", (mktr_id,))
    return {"success": True}


@router.get("/api/admin/marketers/{mktr_id}/referrals")
async def admin_marketer_referrals(mktr_id: int, request: Request, _=Depends(require_admin)):
    db = request.app.state.db
    try:
        rows = db.execute("""
            SELECT r.*, c.name as client_name
            FROM marketer_referrals r
            LEFT JOIN clients c ON c.id = r.client_id
            WHERE r.marketer_id = %s
            ORDER BY r.converted_at DESC
        """, (mktr_id,), fetch="all")
        return {"success": True, "referrals": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "referrals": [], "warning": str(e)}


