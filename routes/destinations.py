#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/m14b_destinations.py
م14ب — وجهات سياحية Tourist Destinations
وحدة اشتراك مستقلة: كتالوج الوجهات، نقاط الاهتمام، التقييمات، الحجوزات
"""
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m14b", tags=["Destinations"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


# ─── كتالوج الوجهات ───────────────────────────────────────────
@router.get("/destinations")
async def list_destinations(request: Request,
                             category: Optional[str] = None,
                             city: Optional[str] = None,
                             session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = "SELECT * FROM tourist_destinations WHERE client_id=%s AND status='active'"
            params = [cid]
            if category:
                q += " AND category=%s"; params.append(category)  # noqa: E702
            if city:
                q += " AND city ILIKE %s"; params.append(f"%{city}%")  # noqa: E702
            q += " ORDER BY name_ar"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_destinations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/destinations")
async def create_destination(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            if not data.get("dest_code"):
                data["dest_code"] = f"DST-{secrets.token_hex(4).upper()}"
            row = db.execute("""
                INSERT INTO tourist_destinations
                    (client_id, dest_code, name_ar, name_en, description_ar,
                     city, category, latitude, longitude,
                     entry_fee_adult, entry_fee_child,
                     opening_hours, website_url,
                     visit_duration_hours, max_group_size, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'active')
                RETURNING *
            """, (cid,
                  data["dest_code"], data.get("name_ar",""), data.get("name_en"),
                  data.get("description_ar"),
                  data.get("city",""), data.get("category","heritage"),
                  data.get("latitude"), data.get("longitude"),
                  float(data.get("entry_fee_adult",0) or 0),
                  float(data.get("entry_fee_child",0) or 0),
                  data.get("opening_hours",""),
                  data.get("website_url"),
                  float(data.get("visit_duration_hours",2) or 2),
                  int(data.get("max_group_size",20) or 20)),
                  fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_destination: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.put("/destinations/{dest_id}")
async def update_destination(dest_id: int, request: Request,
                              session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("""
                UPDATE tourist_destinations
                SET name_ar=%s, description_ar=%s, city=%s, category=%s,
                    entry_fee_adult=%s, entry_fee_child=%s,
                    opening_hours=%s, status=%s
                WHERE id=%s AND client_id=%s
            """, (data.get("name_ar"), data.get("description_ar"),
                  data.get("city"), data.get("category"),
                  float(data.get("entry_fee_adult",0) or 0),
                  float(data.get("entry_fee_child",0) or 0),
                  data.get("opening_hours"), data.get("status","active"),
                  dest_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_destination: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.delete("/destinations/{dest_id}")
async def delete_destination(dest_id: int, request: Request,
                              session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute(
                "UPDATE tourist_destinations SET status='inactive' WHERE id=%s AND client_id=%s",
                (dest_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_destination: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─── نقاط الاهتمام POI ────────────────────────────────────────
@router.get("/destinations/{dest_id}/pois")
async def list_pois(dest_id: int, request: Request,
                    session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT * FROM destination_pois
                WHERE destination_id=%s AND client_id=%s
                ORDER BY name_ar
            """, (dest_id, cid), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_pois: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/destinations/{dest_id}/pois")
async def add_poi(dest_id: int, request: Request,
                  session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO destination_pois
                    (client_id, destination_id, name_ar, poi_type, description_ar, notes)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *
            """, (cid, dest_id,
                  data.get("name_ar",""), data.get("poi_type","attraction"),
                  data.get("description_ar"), data.get("notes")),
                  fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_poi: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─── حجوزات الوجهات ───────────────────────────────────────────
@router.get("/dest-bookings")
async def list_dest_bookings(request: Request,
                              date_from: Optional[str] = None,
                              session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """
                SELECT db.*, d.name_ar as destination_name, g.full_name as guest_name
                FROM destination_bookings db
                LEFT JOIN tourist_destinations d ON db.destination_id = d.id
                LEFT JOIN guests g ON db.guest_id = g.id
                WHERE db.client_id = %s
            """
            params = [cid]
            if date_from:
                q += " AND db.visit_date >= %s"; params.append(date_from)  # noqa: E702
            q += " ORDER BY db.visit_date DESC LIMIT 50"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_dest_bookings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/dest-bookings")
async def book_destination(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            dest = db.execute(
                "SELECT * FROM tourist_destinations WHERE id=%s AND client_id=%s",
                (data.get("destination_id"), cid), fetch="one")
            adults = int(data.get("adults_count", 1))
            children = int(data.get("children_count", 0))
            if dest:
                dest = dict(dest)
                total = (adults * float(dest.get("entry_fee_adult",0))) + \
                        (children * float(dest.get("entry_fee_child",0)))
            else:
                total = float(data.get("total_price", 0))
            row = db.execute("""
                INSERT INTO destination_bookings
                    (client_id, destination_id, guest_id, booking_id,
                     visit_date, visit_time, adults_count, children_count,
                     guide_required, guide_name, total_price, status, notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'confirmed',%s)
                RETURNING *
            """, (cid,
                  data.get("destination_id"), data.get("guest_id"),
                  data.get("booking_id"), data.get("visit_date"),
                  data.get("visit_time"), adults, children,
                  bool(data.get("guide_required", False)),
                  data.get("guide_name"), total,
                  data.get("notes")),
                  fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in book_destination: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─── تقييمات الوجهات ──────────────────────────────────────────
@router.get("/destinations/{dest_id}/reviews")
async def list_reviews(dest_id: int, request: Request,
                        session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT r.*, g.full_name as guest_name
                FROM destination_reviews r
                LEFT JOIN guests g ON r.guest_id = g.id
                WHERE r.destination_id=%s AND r.client_id=%s
                ORDER BY r.created_at DESC
            """, (dest_id, cid), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_reviews: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/destinations/{dest_id}/reviews")
async def add_review(dest_id: int, request: Request,
                     session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO destination_reviews
                    (client_id, destination_id, guest_id,
                     rating, review_text, visit_date)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING *
            """, (cid, dest_id, data.get("guest_id"),
                  int(data.get("rating", 5)),
                  data.get("review_text",""),
                  data.get("visit_date")),
                  fetch="one")
            # تحديث متوسط التقييم
            db.execute("""
                UPDATE tourist_destinations
                SET avg_rating = (
                    SELECT AVG(rating) FROM destination_reviews
                    WHERE destination_id=%s
                ), reviews_count = (
                    SELECT COUNT(*) FROM destination_reviews
                    WHERE destination_id=%s
                )
                WHERE id=%s AND client_id=%s
            """, (dest_id, dest_id, dest_id, cid))
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in add_review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─── إحصاءات ─────────────────────────────────────────────────
@router.get("/stats")
async def destinations_stats(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            total = db.execute(
                "SELECT COUNT(*) as c FROM tourist_destinations WHERE client_id=%s AND status='active'",
                (cid,), fetch="one")
            bookings = db.execute("""
                SELECT COUNT(*) as c, COALESCE(SUM(total_price),0) as rev
                FROM destination_bookings WHERE client_id=%s AND status='confirmed'
            """, (cid,), fetch="one")
            top = db.execute("""
                SELECT d.name_ar, COUNT(db.id) as visits
                FROM destination_bookings db
                JOIN tourist_destinations d ON db.destination_id = d.id
                WHERE db.client_id=%s
                GROUP BY d.name_ar ORDER BY visits DESC LIMIT 5
            """, (cid,), fetch="all")
            bd = dict(bookings) if bookings else {}
            return {
                "success": True,
                "active_destinations": dict(total).get("c",0) if total else 0,
                "total_bookings": bd.get("c",0),
                "total_revenue": float(bd.get("rev",0)),
                "top_destinations": [dict(r) for r in (top or [])],
            }
        return {"success": True, "active_destinations": 0,
                "total_bookings": 0, "total_revenue": 0, "top_destinations": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in destinations_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
