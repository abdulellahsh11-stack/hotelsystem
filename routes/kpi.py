#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M11 — مؤشرات الأداء KPI Analytics"""
import logging
from datetime import date, timedelta
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/m11", tags=["KPI"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/dashboard")
async def kpi_dashboard(request: Request, session=Depends(_require_client)):
    try:
        import asyncio
        db = request.app.state.db
        cid = session["client_id"]
        today = date.today()
        month_start = today.replace(day=1)
        ti = today.isoformat()
        ms = month_start.isoformat()

        if not db.use_postgres:
            return {"success": True, "data": {}}

        async def _safe(coro):
            try:
                return await coro
            except Exception:
                return None

        # All 9 independent reads fire concurrently instead of sequentially
        (rooms_total, occupied, month_rev, pos_rev, month_bk,
         monthly, checkins_today, checkouts_today, staff_count) = await asyncio.gather(
            _safe(db.async_execute("SELECT COUNT(*) as c FROM rooms WHERE client_id=%s", (cid,), fetch="one")),
            _safe(db.async_execute(
                "SELECT COUNT(*) as c FROM bookings WHERE client_id=%s AND status IN ('confirmed','checked_in') AND check_in <= %s AND check_out > %s",
                (cid, ti, ti), fetch="one")),
            _safe(db.async_execute(
                "SELECT COALESCE(SUM(total_room), 0) as s FROM bookings WHERE client_id=%s AND check_in >= %s AND status NOT IN ('cancelled')",
                (cid, ms), fetch="one")),
            _safe(db.async_execute(
                "SELECT COALESCE(SUM(total), 0) as s FROM pos_sales WHERE client_id=%s AND created_at::date >= %s AND status='completed'",
                (cid, ms), fetch="one")),
            _safe(db.async_execute(
                "SELECT COUNT(*) as c FROM bookings WHERE client_id=%s AND check_in >= %s", (cid, ms), fetch="one")),
            _safe(db.async_execute(
                "SELECT TO_CHAR(DATE_TRUNC('month', check_in), 'YYYY-MM') as month, COALESCE(SUM(total_room), 0) as revenue, COUNT(*) as bookings FROM bookings WHERE client_id=%s AND status NOT IN ('cancelled') GROUP BY DATE_TRUNC('month', check_in) ORDER BY DATE_TRUNC('month', check_in) DESC LIMIT 12",
                (cid,), fetch="all")),
            _safe(db.async_execute(
                "SELECT COUNT(*) as c FROM bookings WHERE client_id=%s AND check_in=%s AND status='confirmed'", (cid, ti), fetch="one")),
            _safe(db.async_execute(
                "SELECT COUNT(*) as c FROM bookings WHERE client_id=%s AND check_out=%s AND status='checked_in'", (cid, ti), fetch="one")),
            _safe(db.async_execute(
                "SELECT COUNT(*) as c FROM employees WHERE client_id=%s AND status='active'", (cid,), fetch="one")),
        )

        total_rooms = dict(rooms_total).get("c", 1) if rooms_total else 1
        occupied_rooms = dict(occupied).get("c", 0) if occupied else 0
        occupancy = round((occupied_rooms / max(total_rooms, 1)) * 100, 1)
        revenue_month = float(dict(month_rev).get("s", 0)) if month_rev else 0
        revenue_month += float(dict(pos_rev).get("s", 0)) if pos_rev else 0
        bookings_month = dict(month_bk).get("c", 0) if month_bk else 0
        adr = round(revenue_month / max(occupied_rooms * 30, 1), 2)
        revpar = round(revenue_month / max(total_rooms * 30, 1), 2)

        return {
            "success": True,
            "data": {
                "total_rooms": total_rooms,
                "occupied_rooms": occupied_rooms,
                "occupancy_rate": occupancy,
                "adr": adr,
                "revpar": revpar,
                "revenue_month": revenue_month,
                "bookings_month": bookings_month,
                "checkins_today": dict(checkins_today).get("c", 0) if checkins_today else 0,
                "checkouts_today": dict(checkouts_today).get("c", 0) if checkouts_today else 0,
                "monthly_revenue": [dict(r) for r in (monthly or [])],
                "active_staff": dict(staff_count).get("c", 0) if staff_count else 0,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in kpi_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/revpar")
async def revpar_trend(request: Request, days: int = 30, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute("""
                SELECT kpi_date, occupancy_rate, adr, revpar, revenue_total
                FROM daily_kpis WHERE client_id=%s
                ORDER BY kpi_date DESC LIMIT %s
            """, (cid, days), fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revpar_trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/recalculate")
async def recalculate_kpis(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if not db.use_postgres:
            return {"success": True, "message": "لا يتوفر PostgreSQL"}

        today = date.today()
        total_rooms = db.execute(
            "SELECT COUNT(*) as c FROM rooms WHERE client_id=%s", (cid,), fetch="one")
        total = dict(total_rooms).get("c", 0) if total_rooms else 0

        for i in range(7):
            d = today - timedelta(days=i)
            occ = db.execute("""
                SELECT COUNT(*) as c FROM bookings
                WHERE client_id=%s AND check_in<=%s AND check_out>%s
                AND status IN ('checked_in','confirmed','checked_out')
            """, (cid, d.isoformat(), d.isoformat()), fetch="one")
            occ_count = dict(occ).get("c", 0) if occ else 0
            rev = db.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as s FROM invoices
                WHERE client_id=%s AND issue_date=%s
            """, (cid, d.isoformat()), fetch="one")
            revenue = float(dict(rev).get("s", 0)) if rev else 0
            occ_rate = round((occ_count / max(total, 1)) * 100, 2)
            adr = round(revenue / max(occ_count, 1), 2)
            revpar = round(revenue / max(total, 1), 2)
            db.execute("""
                INSERT INTO daily_kpis
                    (client_id,kpi_date,total_rooms,occupied_rooms,occupancy_rate,
                     adr,revpar,revenue_total,check_ins,check_outs)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,0)
                ON CONFLICT (client_id,kpi_date) DO UPDATE SET
                    occupied_rooms=EXCLUDED.occupied_rooms,
                    occupancy_rate=EXCLUDED.occupancy_rate,
                    adr=EXCLUDED.adr, revpar=EXCLUDED.revpar,
                    revenue_total=EXCLUDED.revenue_total
            """, (cid, d.isoformat(), total, occ_count, occ_rate, adr, revpar, revenue))
        return {"success": True, "message": "تم إعادة احتساب KPIs لآخر 7 أيام"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in recalculate_kpis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/revenue-by-room-type")
async def revenue_by_room_type(request: Request, days: int = 30,
                               session=Depends(_require_client)):
    """
    الإيراد وRevPAR وADR لكل نوع غرفة.

    كان تصدير Excel وPDF يُخرج ورقةً فارغة بعنوان «الإيراد حسب الغرفة»
    لأن مصدرها لم يكن موجوداً أصلاً — لا لأن الوصل نُسي.

    التعريفات المستعملة، صريحةً لأن الخلط بينها شائع:
      ADR    = الإيراد ÷ الليالي **المبيعة**
      RevPAR = الإيراد ÷ الليالي **المتاحة** (الغرف × الأيام)
    الأول يقيس سعر ما بيع، والثاني يقيس ما حقّقته الغرف كلها بما فيها
    الفارغة — فالثاني أصغر دائماً، واختلافهما مقصود.
    """
    db = request.app.state.db
    cid = session["client_id"]
    window = max(1, min(int(days or 30), 365))

    if not getattr(db, "use_postgres", False):
        return {"success": True, "data": []}

    try:
        rows = db.execute(
            """
            WITH stock AS (
                SELECT COALESCE(NULLIF(room_type, ''), 'غير مصنَّف') AS room_type,
                       COUNT(*) AS rooms
                FROM rooms WHERE client_id = %s
                GROUP BY 1
            ),
            sold AS (
                SELECT COALESCE(NULLIF(r.room_type, ''), 'غير مصنَّف') AS room_type,
                       COALESCE(SUM(GREATEST(b.check_out - b.check_in, 0)), 0) AS nights,
                       COALESCE(SUM(b.total_room), 0) AS revenue
                FROM bookings b
                JOIN rooms r ON r.id = b.room_id AND r.client_id = b.client_id
                WHERE b.client_id = %s
                  AND b.status IN ('confirmed', 'checked_in', 'checked_out')
                  AND b.check_in >= CURRENT_DATE - %s::int
                GROUP BY 1
            )
            SELECT stock.room_type,
                   stock.rooms,
                   COALESCE(sold.nights, 0)  AS nights,
                   COALESCE(sold.revenue, 0) AS revenue
            FROM stock LEFT JOIN sold USING (room_type)
            ORDER BY revenue DESC
            """,
            (cid, cid, window), fetch="all") or []
    except Exception as exc:
        logger.error("revenue_by_room_type: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="تعذّر حساب الإيراد حسب النوع") from None

    data = []
    for r in rows:
        row = dict(r)
        revenue = float(row.get("revenue") or 0)
        nights = int(row.get("nights") or 0)
        available = int(row.get("rooms") or 0) * window
        data.append({
            "type": row["room_type"],
            "rooms": int(row.get("rooms") or 0),
            "nights": nights,
            "revenue": round(revenue, 2),
            "adr": round(revenue / nights, 2) if nights else 0.0,
            "revpar": round(revenue / available, 2) if available else 0.0,
            # الإشغال نصّاً لأن الواجهة تعرضه كما هو في جدول التصدير
            "occ": f"{round(nights / available * 100, 1)}%" if available else "0%",
        })
    return {"success": True, "data": data, "days": window}
