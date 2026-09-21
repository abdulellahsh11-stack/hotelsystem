#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M07 — الإشراف الداخلي Housekeeping"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m07", tags=["Housekeeping"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/tasks")
async def list_tasks(request: Request, status: Optional[str] = None,
                     session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT t.*, r.room_number
                   FROM housekeeping_tasks t LEFT JOIN rooms r ON t.room_id = r.id
                   WHERE t.client_id = %s"""
            params = [cid]
            if status:
                q += " AND t.status = %s"
                params.append(status)
            q += " ORDER BY t.created_at DESC LIMIT 100"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/tasks")
async def create_task(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO housekeeping_tasks
                    (client_id,room_id,task_type,priority,assigned_to,status,notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (cid, data.get("room_id"), data.get("task_type", "cleaning"),
                  data.get("priority", "normal"), data.get("assigned_to"),
                  "pending", data.get("notes")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_task: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.put("/tasks/{task_id}/status")
async def update_task_status(task_id: int, request: Request,
                              session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        new_status = data.get("status", "completed")
        staff_name = data.get("staff_name", "")
        if db.use_postgres:
            extra = ""
            if new_status == "in_progress":
                extra = ", started_at = NOW()"
            elif new_status == "completed":
                extra = ", completed_at = NOW()"
            db.execute(
                f"UPDATE housekeeping_tasks SET status=%s, "
                f"assigned_to=COALESCE(NULLIF(%s,''),assigned_to){extra} "
                f"WHERE id=%s AND client_id=%s",
                (new_status, staff_name, task_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_task_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ── Rooms ──────────────────────────────────────────────────────────────────

@router.get("/rooms/status")
async def rooms_status(request: Request, session=Depends(_require_client)):
    """قائمة الغرف مع حالتها وآخر موظف نفّذ إجراءً عليها"""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT room_number, status, floor, room_type,
                       last_action_by, last_action_at,
                       current_guest, checkout_due
                FROM rooms
                WHERE client_id = %s
                ORDER BY floor, room_number
            """, (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rooms_status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/rooms/{room_number}/checkout")
async def checkout_room(room_number: str, request: Request,
                         session=Depends(_require_client)):
    """
    تسجيل خروج الضيف — يتطلب تأكيد نظافة الغرفة.
    يُسجّل اسم الموظف الذي أجرى الفحص ويُحوّل الغرفة إلى وضع التنظيف.
    """
    try:
        data = await request.json()
        staff_name = (data.get("staff_name") or "").strip()
        confirmed = data.get("confirmed_clean", False)

        if not staff_name:
            raise HTTPException(400, "اسم الموظف مطلوب")
        if not confirmed:
            raise HTTPException(400, "يجب تأكيد نظافة الغرفة قبل تسجيل الخروج")

        db = request.app.state.db
        cid = session["client_id"]

        if db.use_postgres:
            room = db.execute(
                "SELECT id, status, current_guest FROM rooms WHERE room_number=%s AND client_id=%s",
                (room_number, cid), fetch="one")
            if not room:
                raise HTTPException(404, f"الغرفة {room_number} غير موجودة")

            prev_status = room["status"]

            db.execute("""
                UPDATE rooms
                SET status        = 'cleaning',
                    last_action_by = %s,
                    last_action_at = NOW(),
                    current_guest  = NULL,
                    checkout_due   = NULL
                WHERE room_number = %s AND client_id = %s
            """, (staff_name, room_number, cid))

            db.execute("""
                INSERT INTO room_actions
                    (client_id, room_number, action_type, performed_by,
                     previous_status, new_status, notes)
                VALUES (%s, %s, 'checkout_inspection', %s, %s, 'cleaning', %s)
            """, (cid, room_number, staff_name, prev_status,
                  f"فحص النظافة وتسجيل الخروج — الضيف: {room.get('current_guest') or 'غير محدد'}"))

            db.execute("""
                INSERT INTO housekeeping_tasks
                    (client_id, room_id, task_type, priority, assigned_to, status, notes)
                VALUES (
                    %s,
                    (SELECT id FROM rooms WHERE room_number=%s AND client_id=%s LIMIT 1),
                    'cleaning', 'high', %s, 'pending',
                    'تنظيف بعد مغادرة — فُحصت بواسطة: ' || %s
                )
            """, (cid, room_number, cid, staff_name, staff_name))

        return {
            "success": True,
            "message": f"تم تسجيل الخروج بواسطة {staff_name} — الغرفة {room_number} جاهزة للتنظيف",
            "staff_name": staff_name,
            "room": room_number,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in checkout_room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/rooms/{room_number}/clean")
async def mark_room_clean(room_number: str, request: Request,
                           session=Depends(_require_client)):
    """تسجيل اكتمال التنظيف — الغرفة تصبح جاهزة"""
    try:
        try:
            data = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
        except Exception:
            data = {}
        staff_name = (data.get("staff_name") or "").strip() if data else ""
        db = request.app.state.db
        cid = session["client_id"]

        if db.use_postgres:
            room = db.execute(
                "SELECT id, status FROM rooms WHERE room_number=%s AND client_id=%s",
                (room_number, cid), fetch="one")
            if not room:
                raise HTTPException(404, f"الغرفة {room_number} غير موجودة")

            db.execute("""
                UPDATE rooms
                SET status        = 'available',
                    last_action_by = %s,
                    last_action_at = NOW()
                WHERE room_number = %s AND client_id = %s
            """, (staff_name or "موظف", room_number, cid))

            if staff_name:
                db.execute("""
                    INSERT INTO room_actions
                        (client_id, room_number, action_type, performed_by,
                         previous_status, new_status, notes)
                    VALUES (%s, %s, 'cleaning_done', %s, %s, 'available', 'اكتمل التنظيف')
                """, (cid, room_number, staff_name, room["status"]))

            db.execute("""
                UPDATE housekeeping_tasks
                SET status       = 'completed',
                    completed_at = NOW(),
                    assigned_to  = COALESCE(NULLIF(%s,''), assigned_to)
                WHERE room_id = %s AND client_id = %s AND status IN ('pending','in_progress')
            """, (staff_name, room["id"], cid))

        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in mark_room_clean: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/rooms/{room_number}/history")
async def room_history(room_number: str, request: Request,
                        session=Depends(_require_client)):
    """سجل الإجراءات على غرفة معينة مع أسماء الموظفين"""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT action_type, performed_by, previous_status, new_status, notes, created_at
                FROM room_actions
                WHERE client_id = %s AND room_number = %s
                ORDER BY created_at DESC
                LIMIT 20
            """, (cid, room_number), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in room_history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ── Lost & Found ───────────────────────────────────────────────────────────

@router.get("/lost-found")
async def list_lost_found(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                "SELECT * FROM lost_and_found WHERE client_id=%s ORDER BY created_at DESC",
                (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_lost_found: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/lost-found")
async def add_lost_found(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO lost_and_found
                    (client_id,room_id,item_description,found_date,found_by,status,notes)
                VALUES (%s,%s,%s,%s,%s,'stored',%s) RETURNING *
            """, (cid, data.get("room_id"), data.get("item_description", ""),
                  data.get("found_date"), data.get("found_by"),
                  data.get("notes")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_lost_found: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
