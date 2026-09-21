#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M10 — CRM والولاء CRM & Loyalty"""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m10", tags=["CRM"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/contacts")
async def list_contacts(request: Request, segment: Optional[str] = None,
                        session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT c.*, g.full_name, g.absher_phone, g.nationality
                   FROM crm_contacts c LEFT JOIN guests g ON c.guest_id = g.id
                   WHERE c.client_id = %s"""
            params = [cid]
            if segment: q += " AND c.segment = %s"; params.append(segment)  # noqa: E701, E702
            q += " ORDER BY c.lifetime_value DESC LIMIT 200"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_contacts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/loyalty/{guest_id}")
async def guest_loyalty(guest_id: int, request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            profile = db.execute(
                "SELECT * FROM guest_profiles WHERE client_id=%s AND guest_id=%s",
                (cid, guest_id), fetch="one")
            txns = db.execute(
                "SELECT * FROM loyalty_transactions WHERE client_id=%s AND guest_id=%s ORDER BY created_at DESC LIMIT 20",
                (cid, guest_id), fetch="all")
            return {
                "success": True,
                "profile": dict(profile) if profile else {},
                "transactions": [dict(r) for r in (txns or [])]
            }
        return {"success": True, "profile": {}, "transactions": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in guest_loyalty: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/loyalty/award")
async def award_points(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("""
                INSERT INTO loyalty_transactions
                    (client_id,guest_id,transaction_type,points,booking_id,description)
                VALUES (%s,%s,'award',%s,%s,%s)
            """, (cid, data.get("guest_id"), int(data.get("points", 0)),
                  data.get("booking_id"), data.get("description", "نقاط مكافأة")))
            db.execute("""
                INSERT INTO guest_profiles (client_id,guest_id,loyalty_points)
                VALUES (%s,%s,%s)
                ON CONFLICT (client_id, guest_id) DO NOTHING
            """, (cid, data.get("guest_id"), 0))
            db.execute("""
                UPDATE guest_profiles SET loyalty_points = loyalty_points + %s
                WHERE client_id=%s AND guest_id=%s
            """, (int(data.get("points", 0)), cid, data.get("guest_id")))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in award_points: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/campaigns")
async def list_campaigns(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                "SELECT * FROM campaigns WHERE client_id=%s ORDER BY created_at DESC",
                (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_campaigns: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/campaigns")
async def create_campaign(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO campaigns
                    (client_id,name,campaign_type,target_segment,
                     message_ar,subject,send_date,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'draft') RETURNING *
            """, (cid, data.get("name", "حملة جديدة"),
                  data.get("campaign_type", "whatsapp"),
                  data.get("target_segment"), data.get("message_ar"),
                  data.get("subject"), data.get("send_date")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_campaign: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/stats")
async def crm_stats(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            total = db.execute("SELECT COUNT(*) as c FROM guests WHERE client_id=%s",
                               (cid,), fetch="one")
            vip = db.execute("SELECT COUNT(*) as c FROM guest_profiles WHERE client_id=%s AND vip_level!='standard'",
                             (cid,), fetch="one")
            pts = db.execute("SELECT SUM(loyalty_points) as s FROM guest_profiles WHERE client_id=%s",
                             (cid,), fetch="one")
            return {
                "success": True,
                "total_guests": dict(total).get("c", 0) if total else 0,
                "vip_guests": dict(vip).get("c", 0) if vip else 0,
                "total_points": dict(pts).get("s", 0) if pts else 0,
            }
        return {"success": True, "total_guests": 0, "vip_guests": 0, "total_points": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in crm_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
