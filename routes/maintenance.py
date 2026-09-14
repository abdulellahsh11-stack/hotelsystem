#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M08 — الصيانة Maintenance"""
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m08", tags=["Maintenance"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/orders")
async def list_orders(request: Request, status: Optional[str] = None,
                      session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT o.*, r.room_number
                   FROM maintenance_orders o LEFT JOIN rooms r ON o.room_id = r.id
                   WHERE o.client_id = %s"""
            params = [cid]
            if status: q += " AND o.status = %s"; params.append(status)  # noqa: E701, E702
            q += " ORDER BY o.created_at DESC LIMIT 100"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_orders: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/orders")
async def create_order(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            from services import maintenance_report
            num = f"MO-{secrets.token_hex(4).upper()}"
            loc_type = maintenance_report.normalize_location(data.get("location_type"))
            loc_label = str(data.get("location_label") or "")[:120] or None
            row = db.execute("""
                INSERT INTO maintenance_orders
                    (client_id,room_id,order_number,issue_type,description,
                     priority,assigned_to,status,estimated_cost,
                     location_type,location_label)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'open',%s,%s,%s) RETURNING *
            """, (cid, data.get("room_id"), num, data.get("issue_type", "general"),
                  data.get("description", ""), data.get("priority", "normal"),
                  data.get("assigned_to"), float(data.get("estimated_cost", 0) or 0),
                  loc_type, loc_label),
                  fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.put("/orders/{order_id}")
async def update_order(order_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            extra = ""
            if data.get("status") == "in_progress":
                extra = ", started_at = NOW()"
            elif data.get("status") == "completed":
                extra = ", completed_at = NOW()"
            db.execute(f"""
                UPDATE maintenance_orders SET status=%s, assigned_to=%s,
                actual_cost=%s, notes=%s{extra}
                WHERE id=%s AND client_id=%s
            """, (data.get("status", "open"), data.get("assigned_to"),
                  float(data.get("actual_cost", 0) or 0), data.get("notes"),
                  order_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/orders/{order_id}/materials")
async def use_materials(order_id: int, request: Request, session=Depends(_require_client)):
    """يخصم مواد الصيانة المستخدَمة في أمرٍ من المستودع (عشرة، استُخدم ثلاثة → سبعة).

    الأمر يجب أن يخصّ هذه المنشأة، والأصناف تُخصَم بمعرّفها معزولةً بالمنشأة.
    """
    try:
        from services import maintenance_stock
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        actor = session.get("username") or session.get("role") or "maintenance"
        if not db.use_postgres:
            return {"success": True, "data": []}
        order = db.execute(
            "SELECT order_number FROM maintenance_orders WHERE id=%s AND client_id=%s",
            (order_id, cid), fetch="one")
        if not order:
            raise HTTPException(status_code=404, detail="أمر الصيانة غير موجود")
        ref = dict(order).get("order_number") or order_id
        used = maintenance_stock.consume(db, cid, data.get("materials"), order_ref=ref, actor=actor)
        return {"success": True, "data": used}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in use_materials: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/orders/{order_id}/complete")
async def complete_order(order_id: int, request: Request, session=Depends(_require_client)):
    """إنجاز تذكرة الصيانة: يُحفظ التقرير وتُخصَم المواد المستخدَمة من مستودع
    الصيانة تلقائياً في خطوةٍ واحدة (سلك · إضاءة · مفتاح…). الأمر يجب أن يخصّ
    هذه المنشأة، والأصناف تُخصَم بمعرّفها معزولةً بالمنشأة (لا هبوط تحت الصفر)."""
    try:
        from services import maintenance_report, maintenance_stock
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        actor = session.get("username") or session.get("role") or "maintenance"
        if not db.use_postgres:
            return {"success": True, "data": {"used": []}}
        order = db.execute(
            "SELECT order_number FROM maintenance_orders WHERE id=%s AND client_id=%s",
            (order_id, cid), fetch="one")
        if not order:
            raise HTTPException(status_code=404, detail="أمر الصيانة غير موجود")
        ref = dict(order).get("order_number") or order_id
        used = maintenance_stock.consume(db, cid, data.get("materials"),
                                         order_ref=ref, actor=actor)
        report = maintenance_report.clean_report(data.get("report"))
        db.execute(
            """UPDATE maintenance_orders
                 SET status='completed', report=%s, actual_cost=%s, completed_at=NOW()
               WHERE id=%s AND client_id=%s""",
            (report, float(data.get("actual_cost", 0) or 0), order_id, cid))
        return {"success": True, "data": {"id": order_id, "status": "completed",
                "report": report, "used": used}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in complete_order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.get("/assets")
async def list_assets(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                "SELECT * FROM assets WHERE client_id=%s ORDER BY name_ar",
                (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_assets: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")


@router.post("/assets")
async def create_asset(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            if not data.get("asset_code"):
                data["asset_code"] = f"AST-{secrets.token_hex(4).upper()}"
            row = db.execute("""
                INSERT INTO assets
                    (client_id,asset_code,name_ar,category,location,
                     purchase_date,purchase_cost,warranty_expiry,status,notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'operational',%s) RETURNING *
            """, (cid, data["asset_code"], data.get("name_ar", ""),
                  data.get("category"), data.get("location"),
                  data.get("purchase_date"), float(data.get("purchase_cost", 0) or 0),
                  data.get("warranty_expiry"), data.get("notes")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_asset: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"خطأ في الخادم: {str(e)}")
