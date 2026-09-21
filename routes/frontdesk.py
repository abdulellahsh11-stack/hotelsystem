#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""routes/m02_frontdesk.py — الاستقبال Front Desk"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

from services.tax_config import get_client_tax_config, calculate_tax as _calc_tax

router = APIRouter(prefix="/api/m02", tags=["FrontDesk"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/arrivals")
async def today_arrivals(request: Request, session=Depends(_require_client)):
    try:
        from datetime import date
        db = request.app.state.db
        cid = session["client_id"]
        today = date.today().isoformat()
        if db.use_postgres:
            rows = db.execute("""
                SELECT b.*,
                       COALESCE(b.vat_amount, 0)         AS vat_amount,
                       COALESCE(b.tourism_tax_amount, 0) AS tourism_tax_amount,
                       COALESCE(b.tax_mode, 'MODE_A')    AS tax_mode,
                       g.full_name, g.id_number, r.room_number
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms r ON b.room_id = r.id
                WHERE b.client_id=%s AND b.check_in=%s AND b.status='confirmed'
                ORDER BY b.check_in
            """, (cid, today), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in today_arrivals: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/departures")
async def today_departures(request: Request, session=Depends(_require_client)):
    try:
        from datetime import date
        db = request.app.state.db
        cid = session["client_id"]
        today = date.today().isoformat()
        if db.use_postgres:
            rows = db.execute("""
                SELECT b.*,
                       COALESCE(b.vat_amount, 0)         AS vat_amount,
                       COALESCE(b.tourism_tax_amount, 0) AS tourism_tax_amount,
                       COALESCE(b.tax_mode, 'MODE_A')    AS tax_mode,
                       g.full_name, r.room_number
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms r ON b.room_id = r.id
                WHERE b.client_id=%s AND b.check_out=%s AND b.status='checked_in'
                ORDER BY b.check_out
            """, (cid, today), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in today_departures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/checkin/{booking_id}")
async def checkin(booking_id: str, request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        data = await request.json()
        if db.use_postgres:
            with db.transaction() as cur:
                cur.execute("""
                    UPDATE bookings SET status='checked_in', actual_check_in=NOW()
                    WHERE id=%s AND client_id=%s AND status='confirmed'
                    RETURNING room_id, guest_id
                """, (booking_id, cid))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(400, "الحجز غير موجود أو لا يمكن تسجيل وصوله (تحقق من الحالة)")
                room_id = row["room_id"]
                guest_id = row["guest_id"]
                cur.execute("""
                    UPDATE rooms SET status='occupied'
                    WHERE id=%s AND client_id=%s
                """, (room_id, cid))
                cur.execute("""
                    INSERT INTO check_in_log
                        (client_id, booking_id, room_id, guest_id, checkin_by, id_verified, key_issued)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (cid, booking_id, room_id, guest_id,
                      data.get("checkin_by", "استقبال"), True, True))
        return {"success": True, "message": "تم تسجيل الوصول بنجاح"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in checkin: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/checkout/{booking_id}")
async def checkout(booking_id: str, request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        data = await request.json()
        room_id = None
        if db.use_postgres:
            with db.transaction() as cur:
                cur.execute("""
                    UPDATE bookings SET status='checked_out', actual_check_out=NOW()
                    WHERE id=%s AND client_id=%s AND status='checked_in'
                    RETURNING room_id
                """, (booking_id, cid))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(400, "الحجز غير موجود أو الضيف لم يُسجَّل وصوله بعد")
                room_id = row["room_id"]
                cur.execute("""
                    UPDATE rooms SET status='cleaning'
                    WHERE id=%s AND client_id=%s
                """, (room_id, cid))
                cur.execute("""
                    INSERT INTO check_out_log
                        (client_id, booking_id, checkout_by, final_amount, payment_method)
                    VALUES (%s, %s, %s, %s, %s)
                """, (cid, booking_id, data.get("checkout_by", "استقبال"),
                      float(data.get("final_amount", 0)), data.get("payment_method", "cash")))

        # تفاصيل الضريبة في إيصال المغادرة
        tax_breakdown = {}
        if db.use_postgres:
            b_row = db.execute("""
                SELECT total_room,
                       COALESCE(vat_amount, 0)         AS vat_amount,
                       COALESCE(tourism_tax_amount, 0) AS tourism_tax_amount,
                       COALESCE(tax_mode, 'MODE_A')    AS tax_mode
                FROM bookings WHERE id=%s AND client_id=%s
            """, (booking_id, cid), fetch="one")
            if b_row:
                br = dict(b_row)
                final_amount = float(data.get("final_amount", 0)) or float(br.get("total_room", 0))
                if float(br.get("vat_amount", 0)) > 0:
                    # استخدام القيم المخزّنة مع الحجز
                    grand = float(br.get("total_room", final_amount))
                    vat   = float(br.get("vat_amount", 0))
                    tour  = float(br.get("tourism_tax_amount", 0))
                    tax_breakdown = {
                        "tax_mode":           br.get("tax_mode", "MODE_A"),
                        "grand_total":        grand,
                        "vat_amount":         vat,
                        "tourism_tax_amount": tour,
                        "net_amount":         round(grand - vat - tour, 2),
                    }
                else:
                    # حساب من المبلغ النهائي عند غياب البيانات المخزّنة
                    cfg = get_client_tax_config(db, cid)
                    t = _calc_tax(amount=final_amount, config=cfg)
                    tax_breakdown = {
                        "tax_mode":           t["tax_mode"],
                        "grand_total":        t["grand_total"],
                        "vat_amount":         t["vat_amount"],
                        "tourism_tax_amount": t["tourism_tax_amount"],
                        "net_amount":         t["net"],
                    }

        return {
            "success": True,
            "message": "تم تسجيل المغادرة بنجاح — الغرفة قيد التنظيف",
            "tax_breakdown": tax_breakdown,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in checkout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/shifts")
async def list_shifts(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                "SELECT * FROM front_desk_shifts WHERE client_id=%s ORDER BY started_at DESC LIMIT 20",
                (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_shifts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/shifts/open")
async def open_shift(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO front_desk_shifts
                    (client_id,employee_name,shift_type,opening_cash,status)
                VALUES (%s,%s,%s,%s,'open') RETURNING *
            """, (cid, data.get("employee_name", "موظف"),
                  data.get("shift_type", "morning"),
                  float(data.get("opening_cash", 0))), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in open_shift: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/shifts/{shift_id}/close")
async def close_shift(shift_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("""
                UPDATE front_desk_shifts SET status='closed', ended_at=NOW(),
                closing_cash=%s, notes=%s WHERE id=%s AND client_id=%s
            """, (float(data.get("closing_cash", 0)), data.get("notes"), shift_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in close_shift: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/rooms/availability")
async def room_availability(request: Request, date_from: Optional[str] = None,
                             date_to: Optional[str] = None, session=Depends(_require_client)):
    try:
        from datetime import date
        db = request.app.state.db
        cid = session["client_id"]
        dfrom = date_from or date.today().isoformat()
        dto = date_to or dfrom
        if db.use_postgres:
            rows = db.execute("""
                SELECT r.*,
                CASE WHEN EXISTS (
                    SELECT 1 FROM bookings b WHERE b.room_id = r.id
                    AND b.status IN ('confirmed','checked_in')
                    AND b.check_in < %s AND b.check_out > %s
                ) THEN 'occupied' ELSE r.status END as current_status
                FROM rooms r WHERE r.client_id=%s ORDER BY r.room_number
            """, (dto, dfrom, cid), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in room_availability: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
