#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M14 — الجولات السياحية Tourism Tours"""
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m14", tags=["Tourism"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/tours")
async def list_tours(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                "SELECT * FROM tour_catalog WHERE client_id=%s AND status='active' ORDER BY name_ar",
                (cid,), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_tours: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/tours")
async def create_tour(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            if not data.get("tour_code"):
                data["tour_code"] = f"TR-{secrets.token_hex(4).upper()}"
            row = db.execute("""
                INSERT INTO tour_catalog
                    (client_id,tour_code,name_ar,name_en,description_ar,
                     tour_type,duration_hours,price_adult,price_child,
                     max_capacity,includes_ar,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active') RETURNING *
            """, (cid, data["tour_code"], data.get("name_ar", ""),
                  data.get("name_en"), data.get("description_ar"),
                  data.get("tour_type", "city"),
                  float(data.get("duration_hours", 3)),
                  float(data.get("price_adult", 0)),
                  float(data.get("price_child", 0)),
                  int(data.get("max_capacity", 10)),
                  data.get("includes_ar")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_tour: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.put("/tours/{tour_id}")
async def update_tour(tour_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("""
                UPDATE tour_catalog SET name_ar=%s,description_ar=%s,
                price_adult=%s,price_child=%s,status=%s
                WHERE id=%s AND client_id=%s
            """, (data.get("name_ar"), data.get("description_ar"),
                  float(data.get("price_adult", 0)),
                  float(data.get("price_child", 0)),
                  data.get("status", "active"), tour_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_tour: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/bookings")
async def list_tour_bookings(request: Request, date_from: Optional[str] = None,
                             session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT tb.*, tc.name_ar as tour_name, g.full_name as guest_name
                   FROM tour_bookings tb
                   LEFT JOIN tour_catalog tc ON tb.tour_id = tc.id
                   LEFT JOIN guests g ON tb.guest_id = g.id
                   WHERE tb.client_id = %s"""
            params = [cid]
            if date_from:
                q += " AND tb.tour_date >= %s"; params.append(date_from)  # noqa: E702
            q += " ORDER BY tb.tour_date DESC LIMIT 50"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_tour_bookings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/bookings")
async def book_tour(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            tour = db.execute(
                "SELECT * FROM tour_catalog WHERE id=%s AND client_id=%s",
                (data.get("tour_id"), cid), fetch="one")
            if tour:
                tour = dict(tour)
                adults = int(data.get("adults_count", 1))
                children = int(data.get("children_count", 0))
                total = (adults * float(tour["price_adult"])) + (children * float(tour["price_child"]))
            else:
                total = float(data.get("total_price", 0))
            row = db.execute("""
                INSERT INTO tour_bookings
                    (client_id,tour_id,guest_id,booking_id,tour_date,tour_time,
                     adults_count,children_count,guide_name,total_price,status,notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'confirmed',%s) RETURNING *
            """, (cid, data.get("tour_id"), data.get("guest_id"),
                  data.get("booking_id"), data.get("tour_date"),
                  data.get("tour_time"), int(data.get("adults_count", 1)),
                  int(data.get("children_count", 0)),
                  data.get("guide_name"), total,
                  data.get("notes")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in book_tour: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/stats")
async def tour_stats(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            total = db.execute(
                "SELECT COUNT(*) as c FROM tour_catalog WHERE client_id=%s AND status='active'",
                (cid,), fetch="one")
            bookings = db.execute(
                "SELECT COUNT(*) as c, COALESCE(SUM(total_price),0) as rev FROM tour_bookings WHERE client_id=%s AND status='confirmed'",
                (cid,), fetch="one")
            bd = dict(bookings) if bookings else {}
            return {
                "success": True,
                "active_tours": dict(total).get("c", 0) if total else 0,
                "total_bookings": bd.get("c", 0),
                "total_revenue": float(bd.get("rev", 0)),
            }
        return {"success": True, "active_tours": 0, "total_bookings": 0, "total_revenue": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in tour_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
