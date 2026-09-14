#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/hotel_ops.py — العمليات الفندقية — الضيوف والحجوزات والفواتير ونقاط البيع والغرف
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import (
    JSONResponse,
)

from app_core import (
    log,
    require_client,
)
from db.access import require_manager

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Guests
# ──────────────────────────────────────────────────────────────
def _may_see_pii(session: dict) -> bool:
    """
    من يرى بيانات النزيل كاملةً؟

    مالك المنشأة ومديرها العام (`*`)، ومدير المناوبة وموظف الاستقبال —
    لأن تسجيل الوصول لا يتمّ بلا رقم هوية. أما الإشراف الداخلي والمحاسب
    والكاشير فيرون الاسم مُقنَّعاً: التنظيف لا يحتاج هوية، والفاتورة
    تُصدَر برقم الحجز.
    """
    from db.security import check_permission

    return check_permission(session, "guests.pii")


def _present(guests: list, session: dict) -> list:
    """يُقنّع ما لا يُصرَّح به. التقنيع عرضٌ لا تخزين."""
    if _may_see_pii(session):
        return guests
    from services.guest_crypto import mask_guest

    return [mask_guest(g) for g in guests]


@router.get("/api/guests")
async def get_guests(request: Request, limit: int = 100, session=Depends(require_client)):
    store = request.app.state.store
    guests = store.get_guests(session["client_id"])
    return {"success": True, "data": _present(guests[:limit], session)}


@router.get("/api/guests/required-fields")
async def guest_required_fields(request: Request, session=Depends(require_client)):
    """الحقول المعروفة والإلزامية لهذه المنشأة — تبني عليها الواجهة التحقّق."""
    from services import guest_fields
    client = request.app.state.store.get_client(session["client_id"]) or {}
    return {"success": True, "data": {
        "fields": guest_fields.GUEST_FIELDS,
        "required": guest_fields.get_required(client),
    }}


@router.post("/api/guests/required-fields")
async def set_guest_required_fields(request: Request, session=Depends(require_manager)):
    """يحفظ الحقول الإلزامية — مالك المنشأة/المدير وحدهما.

    يُقرأ السجل كاملاً ويُعاد حفظه كي لا تُمَسّ بقيّة الإعدادات (ومنها حقول
    الحساب في `_account`)."""
    from services import guest_fields
    data = await request.json()
    fields = guest_fields.sanitize(data.get("required") or [])
    store = request.app.state.store
    client = store.get_client(session["client_id"])
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    settings = dict(client.get("settings") or {})
    settings["guest_required_fields"] = fields
    client["settings"] = settings
    store.save_client(client)
    return {"success": True, "data": {"required": fields}}


@router.post("/api/guests")
async def save_guest(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    # الحقول الإلزامية تُفرَض على الخادم — واجهةٌ تتحقّق وحدها لا تكفي.
    from services import guest_fields
    try:
        _client = store.get_client(session["client_id"]) or {}
    except Exception:
        _client = {}
    _missing = guest_fields.missing_required(data, guest_fields.get_required(_client))
    if _missing:
        raise HTTPException(status_code=422, detail={
            "error": "حقول إلزامية ناقصة",
            "fields": _missing,
        })
    # `guests.id` عمود SERIAL تُسنده قاعدة البيانات — بخلاف `bookings.id`
    # الذي هو VARCHAR فيصحّ فيه معرّفٌ مولَّد. اختراع معرّفٍ ست عشري هنا
    # كان يُسقط الحفظ بـ٥٠٠ في كل مرة (`int()` على نصٍّ ست عشري داخل
    # `get_guest`) — فلم يُحفظ نزيلٌ واحد عبر هذا المسار قط.
    if not str(data.get("id") or "").isdigit():
        data.pop("id", None)
    data["client_id"] = session["client_id"]
    data.setdefault("created_at", datetime.now().isoformat())
    guest = store.save_guest(session["client_id"], data)
    return {"success": True, "data": _present([guest], session)[0]}


@router.get("/api/guests/{guest_id}")
async def get_guest(guest_id: str, request: Request, session=Depends(require_client)):
    store = request.app.state.store
    guests = store.get_guests(session["client_id"])
    guest = next((g for g in guests if str(g.get("id")) == guest_id), None)
    if not guest:
        raise HTTPException(status_code=404, detail="الضيف غير موجود")
    return {"success": True, "data": _present([guest], session)[0]}


# ──────────────────────────────────────────────────────────────
#  Bookings
# ──────────────────────────────────────────────────────────────
@router.get("/api/bookings")
async def get_bookings(
    request: Request, status: Optional[str] = None, limit: int = 100,
    session=Depends(require_client)
):
    store = request.app.state.store
    bookings = store.get_bookings(session["client_id"], status)
    return {"success": True, "data": bookings[:limit]}


@router.post("/api/bookings")
async def save_booking(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("status", "confirmed")
    data.setdefault("created_at", datetime.now().isoformat())
    booking = store.save_booking(session["client_id"], data)
    return {"success": True, "data": booking}


@router.put("/api/bookings/{booking_id}")
async def update_booking(booking_id: str, request: Request, session=Depends(require_client)):
    data = await request.json()
    data["id"] = booking_id
    data["client_id"] = session["client_id"]
    store = request.app.state.store
    booking = store.save_booking(session["client_id"], data)
    return {"success": True, "data": booking}


# ──────────────────────────────────────────────────────────────
#  رحلة تسجيل الدخول — العقد ثم الضيافة (البند ٦)
# ──────────────────────────────────────────────────────────────
@router.get("/api/hospitality/consumables")
async def get_hospitality_consumables(request: Request, session=Depends(require_client)):
    """أصناف الضيافة وكميّاتها لهذه المنشأة — تُخصَم عند تسجيل الدخول."""
    from services import hospitality
    client = request.app.state.store.get_client(session["client_id"]) or {}
    return {"success": True, "data": {"consumables": hospitality.get_consumables(client)}}


@router.post("/api/hospitality/consumables")
async def set_hospitality_consumables(request: Request, session=Depends(require_manager)):
    """يحفظ أصناف الضيافة — المالك/المدير. يُعاد حفظ السجل كاملاً كي لا
    تُمَسّ بقيّة الإعدادات (ومنها _account)."""
    from services import hospitality
    data = await request.json()
    items = hospitality.sanitize(data.get("consumables") or [])
    store = request.app.state.store
    client = store.get_client(session["client_id"])
    if not client:
        raise HTTPException(status_code=404, detail="المنشأة غير موجودة")
    settings = dict(client.get("settings") or {})
    settings["hospitality_consumables"] = items
    client["settings"] = settings
    store.save_client(client)
    return {"success": True, "data": {"consumables": items}}


@router.post("/api/bookings/{booking_id}/checkin")
async def checkin_booking(booking_id: str, request: Request, session=Depends(require_client)):
    """تسجيل دخول النزيل: لا يتمّ حتى يُوقَّع العقد، وعنده تُخصَم الضيافة
    من المخزون ويصير الحجز `checked_in` (الإشارة الخضراء في قائمة النزلاء)."""
    from services import hospitality
    data = await request.json()
    if not hospitality.can_check_in(data.get("contract_signed")):
        raise HTTPException(status_code=403, detail="يجب توقيع العقد قبل تسجيل الدخول")

    store = request.app.state.store
    cid = session["client_id"]
    booking = store.get_booking(cid, booking_id) if hasattr(store, "get_booking") else None
    if not booking:
        booking = next((b for b in store.get_bookings(cid)
                        if str(b.get("id")) == str(booking_id)), None)
    if not booking:
        raise HTTPException(status_code=404, detail="الحجز غير موجود")

    booking = dict(booking)
    booking["status"] = "checked_in"
    store.save_booking(cid, booking)

    consumed = {}
    try:
        client = store.get_client(cid) or {}
        plan = hospitality.plan_consumption(
            hospitality.get_consumables(client),
            nights=int(data.get("nights", 1) or 1),
            guests=int(data.get("guests", 1) or 1),
        )
        consumed = hospitality.apply_consumption(request.app.state.db, cid, plan)
    except Exception:
        # خصم الضيافة أفضل-جهد: لا يمنع تسجيل الدخول، ولا يسقط صامتاً
        log.warning("تعذّر خصم الضيافة عند تسجيل دخول الحجز %s", booking_id)

    # الاستهلاك التلقائي لكل نزيل (مستهلَك يَنقص · فوط نظيفة→متّسخة).
    # الأشخاص = النزيل + مرافقوه.
    try:
        from services import stock_consumption
        persons = int(data.get("guests", 1) or 1) + int(data.get("companions", 0) or 0)
        stock_consumption.consume_for_stay(request.app.state.db, cid, persons,
                                           booking_id=str(booking_id))
    except Exception:
        log.warning("تعذّر استهلاك المخزون التلقائي للحجز %s", booking_id)

    # المحاسبة الفورية (البند ٨): يُحتسَب المبلغ المدفوع مباشرة إن أُرسل.
    payment = None
    try:
        from services import payments
        payment = payments.record(request.app.state.db, cid,
                                  data.get("amount"),
                                  data.get("payment_method", "cash"),
                                  reference=str(booking_id),
                                  device_id=data.get("device_id"))
    except Exception:
        log.warning("تعذّر تسجيل دفعة تسجيل الدخول للحجز %s", booking_id)

    return {"success": True, "data": {
        "id": booking_id, "status": "checked_in",
        "consumed": consumed, "payment": payment}}


# ──────────────────────────────────────────────────────────────
#  الدفعات — تسجيلٌ فوري وتقرير اليوم (البند ٨)
# ──────────────────────────────────────────────────────────────
@router.get("/api/payments")
async def list_payments(request: Request, limit: int = 100, session=Depends(require_client)):
    db = request.app.state.db
    cid = session["client_id"]
    if getattr(db, "use_postgres", False):
        rows = db.execute(
            "SELECT * FROM payments WHERE client_id=%s ORDER BY created_at DESC LIMIT %s",
            (cid, limit), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    return {"success": True, "data": []}


@router.post("/api/payments")
async def create_payment(request: Request, session=Depends(require_client)):
    """يُسجّل دفعةً فورية (نقدي/نقاط بيع) مربوطةً بمرجعٍ اختياري (حجز)."""
    from services import payments
    data = await request.json()
    rec = payments.record(request.app.state.db, session["client_id"],
                         data.get("amount"), data.get("method", "cash"),
                         reference=data.get("reference"),
                         device_id=data.get("device_id"))
    if rec is None:
        raise HTTPException(status_code=400, detail="مبلغ الدفعة غير صالح")
    return {"success": True, "data": rec}


# ──────────────────────────────────────────────────────────────
#  Invoices
# ──────────────────────────────────────────────────────────────
@router.get("/api/invoices")
async def get_invoices(request: Request, limit: int = 100, session=Depends(require_client)):
    store = request.app.state.store
    invoices = store.get_invoices(session["client_id"])
    return {"success": True, "data": invoices[:limit]}


@router.post("/api/invoices")
async def save_invoice(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    if not data.get("id"):
        seq = store.get_next_invoice_seq(cid)
        data["id"] = f"INV-{seq:05d}"
    data["client_id"] = cid
    data.setdefault("created_at", datetime.now().isoformat())
    invoice = store.save_invoice(cid, data)
    return {"success": True, "data": invoice}


# ──────────────────────────────────────────────────────────────
#  POS Transactions
# ──────────────────────────────────────────────────────────────
@router.get("/api/pos")
async def get_pos(
    request: Request, date_from: Optional[str] = None, date_to: Optional[str] = None,
    session=Depends(require_client)
):
    store = request.app.state.store
    txns = store.get_pos_transactions(session["client_id"], date_from, date_to)
    return {"success": True, "data": txns}


@router.post("/api/pos")
async def save_pos(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    if not data.get("id"):
        data["id"] = secrets.token_hex(8)
    data["client_id"] = session["client_id"]
    data.setdefault("created_at", datetime.now().isoformat())
    tx = store.save_pos_transaction(session["client_id"], data)
    return {"success": True, "data": tx}


# ──────────────────────────────────────────────────────────────
#  Settings
# ──────────────────────────────────────────────────────────────
@router.get("/api/settings")
async def get_settings(request: Request, session=Depends(require_client)):
    from db.store import public_settings

    store = request.app.state.store
    client = store.get_client(session["client_id"]) or {}
    return {"success": True, "data": public_settings(client)}


@router.post("/api/settings")
async def save_settings(request: Request, session=Depends(require_client)):
    data = await request.json()
    store = request.app.state.store
    cid = session["client_id"]
    client = store.get_client(cid) or {"id": cid}
    client["settings"] = data
    store.save_client(client)
    return {"success": True}


# ──────────────────────────────────────────────────────────────
#  Rooms
# ──────────────────────────────────────────────────────────────
def _require(session: dict, permission: str) -> None:
    """
    يمنع من لا يملك الصلاحية.

    مسارات الغرف كانت مفتوحةً لأي جلسة: موظف نظافة يستطيع حذف غرفة، وكاشير
    يستطيع تغيير الأسعار. الجلسة تُثبت **من** أنت لا **ماذا يحقّ لك**.
    """
    from db.security import check_permission

    if not check_permission(session, permission):
        raise HTTPException(status_code=403, detail=f"الصلاحية '{permission}' مطلوبة")


# ── خريطة الغرف: التخصيص ───────────────────────────────────────
ROOM_MAP_MAX_LABEL = 80


def _floor_prefs(db, client_id: str) -> dict:
    """تخصيص الأدوار كما ضبطه المشترك. الغياب يعني «الافتراضي» لا «مخفي»."""
    try:
        rows = db.execute(
            "SELECT floor, label, sort_order, is_hidden FROM room_map_floors "
            "WHERE client_id=%s", (client_id,), fetch="all") or []
    except Exception:
        return {}                       # الجدول لم يُرحَّل بعد — الافتراضي يكفي
    return {int(r["floor"]): dict(r) for r in rows}


@router.get("/api/rooms/map")
async def get_room_map(request: Request, session=Depends(require_client)):
    """
    الخريطة جاهزةً للعرض: أدوارٌ مرتَّبة بأسمائها المخصَّصة وغرفها.

    يُبنى هنا لا في المتصفّح، فتراه كل شاشة بنفس الترتيب والأسماء —
    شاشة التسجيل والاستقبال ولوحة التحكم.
    """
    _require(session, "rooms.read")
    db = request.app.state.db
    cid = session["client_id"]

    rows = db.execute(
        "SELECT id, room_number, room_type, floor, capacity, base_price, status, notes "
        "FROM rooms WHERE client_id=%s ORDER BY room_number", (cid,), fetch="all") or []
    prefs = _floor_prefs(db, cid)

    by_floor: dict = {}
    for row in rows:
        room = dict(row)
        floor = 0 if room.get("floor") is None else int(room["floor"])
        by_floor.setdefault(floor, []).append(room)

    can_edit = False
    from db.security import check_permission
    can_edit = check_permission(session, "rooms.write")

    floors = []
    for floor in sorted(by_floor):
        pref = prefs.get(floor, {})
        if pref.get("is_hidden"):
            continue
        floors.append({
            "floor": floor,
            "label": pref.get("label") or ("الدور الأرضي" if floor == 0 else f"الدور {floor}"),
            "customized": bool(pref.get("label")),
            "sort_order": pref.get("sort_order") if pref.get("sort_order") is not None else floor,
            "rooms": sorted(by_floor[floor],
                            key=lambda r: str(r.get("room_number") or "")),
        })
    floors.sort(key=lambda f: (f["sort_order"], f["floor"]))

    hidden = [f for f in prefs.values() if f.get("is_hidden")]
    return {
        "success": True,
        "data": {"floors": floors, "can_edit": can_edit,
                 "hidden_count": len(hidden), "total_rooms": len(rows)},
    }


@router.put("/api/rooms/map/floors")
async def save_room_map(request: Request, session=Depends(require_client)):
    """
    يحفظ تخصيص الأدوار: الاسم والترتيب والإخفاء.

    الإخفاء عرضٌ لا حذف — الغرف تبقى وتُحجز وتُحاسَب، ولا تُعرض في
    الخريطة. من أراد إيقاف غرفة فعلياً يُغيّر حالتها إلى «موقوفة».
    """
    _require(session, "rooms.write")
    data = await request.json()
    floors = data.get("floors")
    if not isinstance(floors, list):
        raise HTTPException(status_code=400, detail="يلزم إرسال قائمة الأدوار")
    if len(floors) > 200:
        raise HTTPException(status_code=400, detail="عدد الأدوار أكبر من المعقول")

    db = request.app.state.db
    cid = session["client_id"]
    saved = 0
    for item in floors:
        if not isinstance(item, dict):
            continue
        try:
            floor = int(item.get("floor"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="رقم الدور يجب أن يكون عدداً") from None
        label = str(item.get("label") or "").strip()[:ROOM_MAP_MAX_LABEL]
        try:
            order = int(item.get("sort_order") if item.get("sort_order") is not None else floor)
        except (TypeError, ValueError):
            order = floor
        db.execute(
            """INSERT INTO room_map_floors (client_id, floor, label, sort_order, is_hidden, updated_at)
               VALUES (%s,%s,%s,%s,%s,NOW())
               ON CONFLICT (client_id, floor) DO UPDATE
                   SET label=EXCLUDED.label, sort_order=EXCLUDED.sort_order,
                       is_hidden=EXCLUDED.is_hidden, updated_at=NOW()""",
            (cid, floor, label or None, order, bool(item.get("is_hidden"))))
        saved += 1

    log.info("حُفظ تخصيص خريطة الغرف (%s دور) للمنشأة %s", saved, cid)
    return {"success": True, "data": {"saved": saved}}


@router.patch("/api/rooms/{room_id}/status")
async def set_room_status(room_id: int, request: Request,
                          session=Depends(require_client)):
    """تغيير حالة غرفة من الخريطة مباشرةً — بصلاحية الكتابة لا بالعرض."""
    _require(session, "rooms.write")
    data = await request.json()
    status = str(data.get("status") or "").strip()
    if status not in ROOM_STATUSES:
        raise HTTPException(status_code=400,
                            detail=f"حالة غير معروفة. المسموح: {'، '.join(ROOM_STATUSES)}")
    db = request.app.state.db
    affected = db.execute(
        "UPDATE rooms SET status=%s WHERE id=%s AND client_id=%s",
        (status, room_id, session["client_id"]))
    if not affected:
        raise HTTPException(status_code=404, detail="الغرفة غير موجودة")
    return {"success": True, "data": {"id": room_id, "status": status}}


@router.get("/api/rooms")
async def get_rooms(request: Request, session=Depends(require_client)):
    _require(session, "rooms.read")
    db = request.app.state.db
    cid = session["client_id"]
    try:
        rows = db.execute(
            "SELECT * FROM rooms WHERE client_id=%s ORDER BY room_number", (cid,), fetch="all"
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "data": [], "warning": str(e)}


ROOM_STATUSES = ("available", "occupied", "dirty", "maintenance", "blocked")


def _clean_room_payload(data: dict) -> dict:
    """
    يتحقق من بيانات الغرفة ويُطبّعها، ويرمي ValueError برسالة عربية.

    التحقق هنا لا في الواجهة وحدها: الـAPI عامٌّ لمن يملك جلسة، والاعتماد
    على المتصفح في التحقق يعني أن أي طلب مباشر يكتب بيانات فاسدة.
    """
    number = str(data.get("room_number") or "").strip()
    if not number:
        raise ValueError("رقم الغرفة مطلوب")
    if len(number) > 20:
        raise ValueError("رقم الغرفة أطول من ٢٠ محرفاً")

    try:
        capacity = int(data.get("capacity") or 2)
    except (TypeError, ValueError):
        raise ValueError("سعة الغرفة يجب أن تكون رقماً") from None
    if not 1 <= capacity <= 50:
        raise ValueError("سعة الغرفة يجب أن تكون بين ١ و٥٠")

    try:
        price = float(data.get("base_price") or 0)
    except (TypeError, ValueError):
        raise ValueError("السعر يجب أن يكون رقماً") from None
    if price < 0:
        raise ValueError("السعر لا يكون سالباً")

    try:
        floor = int(data.get("floor") or 1)
    except (TypeError, ValueError):
        raise ValueError("الطابق يجب أن يكون رقماً") from None

    status = str(data.get("status") or "available").strip()
    if status not in ROOM_STATUSES:
        raise ValueError(f"حالة غير معروفة. المسموح: {'، '.join(ROOM_STATUSES)}")

    return {
        "room_number": number,
        "room_type": str(data.get("room_type") or "standard").strip()[:100],
        "floor": floor,
        "capacity": capacity,
        "base_price": price,
        "status": status,
        "notes": str(data.get("notes") or "").strip()[:1000],
    }


@router.post("/api/rooms")
async def save_room(request: Request, session=Depends(require_client)):
    """يُسجّل غرفة جديدة أو يُعدّل قائمة. `id` في الجسم يعني تعديلاً."""
    _require(session, "rooms.write")
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    room_id = data.get("id")

    try:
        room = _clean_room_payload(data)
    except ValueError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    try:
        if room_id:
            db.execute(
                """UPDATE rooms SET room_number=%s,room_type=%s,floor=%s,
                   capacity=%s,base_price=%s,status=%s,notes=%s
                   WHERE id=%s AND client_id=%s""",
                (room["room_number"], room["room_type"], room["floor"],
                 room["capacity"], room["base_price"], room["status"],
                 room["notes"], room_id, cid)
            )
        else:
            db.execute(
                """INSERT INTO rooms(client_id,room_number,room_type,floor,
                                     capacity,base_price,status,notes)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (cid, room["room_number"], room["room_type"], room["floor"],
                 room["capacity"], room["base_price"], room["status"], room["notes"])
            )
        return {"success": True, "data": room}
    except Exception as exc:
        # القيد UNIQUE(client_id, room_number) هو الخطأ المتوقّع هنا؛
        # رسالة قاعدة البيانات الخام غير مفهومة لصاحب المنشأة.
        text = str(exc).lower()
        if "unique" in text or "duplicate" in text:
            return JSONResponse(
                {"success": False, "error": f"الغرفة رقم {room['room_number']} مسجَّلة مسبقاً"},
                status_code=409,
            )
        log.error("فشل حفظ الغرفة للمنشأة %s: %s", cid, exc, exc_info=True)
        return JSONResponse(
            {"success": False, "error": "تعذّر حفظ الغرفة"}, status_code=500
        )


@router.post("/api/rooms/bulk")
async def create_rooms_bulk(request: Request, session=Depends(require_client)):
    """
    ينشئ غرف عدّة أدوارٍ دفعةً واحدة بترقيمٍ منتظم.

    تسجيل فندقٍ من أربعة أدوار × عشر غرف يدوياً أربعون نموذجاً — عملٌ
    يُملّ فيُهجَر، فتبقى المنصة بلا غرف وتبدو معطّلة. هنا يُوصف النمط
    مرةً واحدة: `floors=4, rooms_per_floor=10` يُنتج ١٠١…١١٠، ٢٠١…٢١٠…

    الغرف الموجودة تُتخطّى ولا تُستبدل — إعادة التشغيل بعد إضافة دورٍ
    جديد يجب أن تكون آمنة، وحذفُ غرفةٍ عليها حجزٌ قائم فسادُ بيانات.
    """
    _require(session, "rooms.write")
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]

    def _int(key, default, low, high, label):
        try:
            value = int(data.get(key) if data.get(key) is not None else default)
        except (TypeError, ValueError):
            raise ValueError(f"{label} يجب أن يكون رقماً") from None
        if not low <= value <= high:
            raise ValueError(f"{label} يجب أن يكون بين {low} و{high}")
        return value

    try:
        floors = _int("floors", 1, 1, 50, "عدد الأدوار")
        per_floor = _int("rooms_per_floor", 1, 1, 100, "عدد الغرف في الدور")
        first_floor = _int("first_floor", 1, 0, 200, "رقم أول دور")
        start = _int("start_number", 1, 1, 99, "رقم أول غرفة في الدور")
        digits = _int("digits", 2, 1, 3, "خانات رقم الغرفة")
        capacity = _int("capacity", 2, 1, 50, "السعة")
        price = float(data.get("base_price") or 0)
        if price < 0:
            raise ValueError("السعر لا يكون سالباً")
    except ValueError as exc:
        return JSONResponse({"success": False, "error": str(exc)}, status_code=400)

    if floors * per_floor > 500:
        return JSONResponse(
            {"success": False, "error": "الحدّ ٥٠٠ غرفة في العملية الواحدة"},
            status_code=400,
        )

    room_type = str(data.get("room_type") or "standard").strip()[:100]

    # الأرقام الموجودة تُقرأ مرةً واحدة: سؤال قاعدة البيانات لكل غرفة
    # يعني مئات الرحلات لعملية واحدة.
    existing = {
        str(r["room_number"]) for r in (db.execute(
            "SELECT room_number FROM rooms WHERE client_id=%s", (cid,), fetch="all"
        ) or [])
    }

    created, skipped = [], []
    for i in range(floors):
        floor_no = first_floor + i
        for j in range(per_floor):
            number = f"{floor_no}{str(start + j).zfill(digits)}"
            if number in existing:
                skipped.append(number)
                continue
            try:
                db.execute(
                    """INSERT INTO rooms(client_id,room_number,room_type,floor,
                                         capacity,base_price,status,notes)
                       VALUES(%s,%s,%s,%s,%s,%s,'available','')""",
                    (cid, number, room_type, floor_no, capacity, price),
                )
                created.append(number)
                existing.add(number)
            except Exception as exc:
                # سباقٌ مع تسجيلٍ متزامن، أو قيدٌ آخر — تُتخطّى الغرفة
                # ولا تُلغى العملية كلها: أربعون غرفةً تضيع بسبب واحدة.
                log.warning("تعذّر إنشاء الغرفة %s للمنشأة %s: %s", number, cid, exc)
                skipped.append(number)

    log.info("أُنشئت %s غرفة للمنشأة %s (تُخطّيت %s)", len(created), cid, len(skipped))
    return {
        "success": True,
        "data": {"created": created, "skipped": skipped,
                 "created_count": len(created), "skipped_count": len(skipped)},
    }


@router.delete("/api/rooms/{room_id}")
async def delete_room(room_id: int, request: Request, session=Depends(require_client)):
    """
    يحذف غرفة. يُرفض الحذف إن كانت مرتبطة بحجوزات قائمة.

    الحذف الصامت لغرفة عليها حجز يترك الحجز معلّقاً بلا غرفة، وهو فساد
    بيانات يظهر متأخّراً عند وصول الضيف.
    """
    _require(session, "rooms.write")
    db = request.app.state.db
    cid = session["client_id"]
    try:
        row = db.execute(
            "SELECT room_number FROM rooms WHERE id=%s AND client_id=%s",
            (room_id, cid), fetch="one"
        )
        if not row:
            raise HTTPException(status_code=404, detail="الغرفة غير موجودة")

        active = db.execute(
            """SELECT COUNT(*) AS n FROM bookings
               WHERE client_id=%s AND room_number=%s
                 AND status IN ('confirmed','checked_in')""",
            (cid, row["room_number"]), fetch="one"
        )
        if active and (active.get("n") or 0) > 0:
            raise HTTPException(
                status_code=409,
                detail=f"لا يمكن حذف الغرفة — عليها {active['n']} حجز قائم",
            )

        db.execute("DELETE FROM rooms WHERE id=%s AND client_id=%s", (room_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        log.error("فشل حذف الغرفة %s للمنشأة %s: %s", room_id, cid, exc, exc_info=True)
        return JSONResponse(
            {"success": False, "error": "تعذّر حذف الغرفة"}, status_code=500
        )


