#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cross-module analytics aggregation — parallel queries via asyncio.gather"""
import asyncio
import logging
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


async def _safe(coro, label: str):
    """Run an async query, return empty dict on any error."""
    try:
        return await coro
    except Exception as e:
        logger.warning(f"analytics {label}: {e}")
        return None


@router.get("/overview")
async def analytics_overview(request: Request, session=Depends(_require_client)):
    """Aggregate KPIs from all modules — 7 queries run in parallel via asyncio.gather."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "data": {}}

        # All 7 queries fire concurrently — no sequential event-loop blocking
        (guests_r, bookings_r, rooms_r, staff_r,
         inventory_r, maintenance_r, pos_r) = await asyncio.gather(
            _safe(db.async_execute(
                "SELECT COUNT(*) as total_guests, COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as new_guests FROM guests WHERE client_id=%s",
                (cid,), fetch="one"), "guests"),
            _safe(db.async_execute(
                "SELECT COUNT(*) as total_bookings, COUNT(*) FILTER (WHERE status='checked_in') as active, COUNT(*) FILTER (WHERE status='confirmed') as confirmed, COALESCE(SUM(total_room) FILTER (WHERE status NOT IN ('cancelled')), 0) as total_revenue, COALESCE(SUM(total_room) FILTER (WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW()) AND status NOT IN ('cancelled')), 0) as month_revenue FROM bookings WHERE client_id=%s",
                (cid,), fetch="one"), "bookings"),
            _safe(db.async_execute(
                "SELECT COUNT(*) as total_rooms, COUNT(*) FILTER (WHERE status='available') as available, COUNT(*) FILTER (WHERE status='occupied') as occupied, COUNT(*) FILTER (WHERE status='cleaning') as cleaning FROM rooms WHERE client_id=%s",
                (cid,), fetch="one"), "rooms"),
            _safe(db.async_execute(
                "SELECT COUNT(*) as total, COUNT(*) FILTER (WHERE status='active') as active FROM employees WHERE client_id=%s",
                (cid,), fetch="one"), "staff"),
            _safe(db.async_execute(
                "SELECT COUNT(*) as low_stock_items FROM warehouse_items WHERE client_id=%s AND reorder_level > 0 AND quantity <= reorder_level",
                (cid,), fetch="one"), "inventory"),
            _safe(db.async_execute(
                "SELECT COUNT(*) as open_orders, COUNT(*) FILTER (WHERE priority='urgent') as urgent FROM maintenance_orders WHERE client_id=%s AND status IN ('open','in_progress')",
                (cid,), fetch="one"), "maintenance"),
            _safe(db.async_execute(
                "SELECT COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) as today_sales, COALESCE(SUM(total) FILTER (WHERE created_at::date = CURRENT_DATE), 0) as today_revenue FROM pos_sales WHERE client_id=%s AND status='completed'",
                (cid,), fetch="one"), "pos"),
        )

        result = {
            "guests":      dict(guests_r)      if guests_r      else {},
            "bookings":    dict(bookings_r)    if bookings_r    else {},
            "rooms":       dict(rooms_r)       if rooms_r       else {},
            "staff":       dict(staff_r)       if staff_r       else {},
            "inventory":   dict(inventory_r)   if inventory_r   else {},
            "maintenance": dict(maintenance_r) if maintenance_r else {},
            "pos":         dict(pos_r)         if pos_r         else {"today_sales": 0, "today_revenue": 0},
        }
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in analytics_overview: {e}", exc_info=True)
        raise HTTPException(500, detail="خطأ في الخادم")


@router.get("/revenue-trend")
async def revenue_trend(request: Request, months: int = 6, session=Depends(_require_client)):
    """Monthly revenue trend for charts."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "data": []}
        rows = await db.async_execute(
            "SELECT TO_CHAR(DATE_TRUNC('month', check_in), 'YYYY-MM') as month, COALESCE(SUM(total_room), 0) as revenue, COUNT(*) as bookings FROM bookings WHERE client_id=%s AND status NOT IN ('cancelled') AND check_in >= NOW() - (%s || ' months')::INTERVAL GROUP BY DATE_TRUNC('month', check_in) ORDER BY DATE_TRUNC('month', check_in)",
            (cid, months), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revenue_trend: {e}", exc_info=True)
        raise HTTPException(500, detail="خطأ في الخادم")


@router.get("/occupancy-heatmap")
async def occupancy_heatmap(request: Request, session=Depends(_require_client)):
    """Room occupancy by day of week — for heatmap visualization."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "data": []}
        rows = await db.async_execute(
            "SELECT EXTRACT(DOW FROM check_in) as day_of_week, COUNT(*) as bookings, COALESCE(AVG(EXTRACT(EPOCH FROM (check_out::timestamp - check_in::timestamp)) / 86400), 0) as avg_nights FROM bookings WHERE client_id=%s AND status NOT IN ('cancelled') AND check_in >= NOW() - INTERVAL '90 days' GROUP BY day_of_week ORDER BY day_of_week",
            (cid,), fetch="all")
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in occupancy_heatmap: {e}", exc_info=True)
        raise HTTPException(500, detail="خطأ في الخادم")
