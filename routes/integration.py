#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/integration.py — محرك الترابط بين البرامج (Cross-Module Orchestration)

حدث عمل واحد (تسجيل نزيل + دفع) يتسلسل أتمياً عبر كل البرامج:

    تسجيل الوصول + الدفع
        ├─ 1. الحجز        → checked_in
        ├─ 2. الغرفة       → occupied        (الإشغال يرتفع)
        ├─ 3. المحاسبة     → قيد إيراد        (revenue_transactions)
        ├─ 4. المخزون      → خصم طقم الضيافة  (warehouse_items + movements)
        ├─ 5. مؤشرات KPI   → daily_kpis      (إشغال/إيراد/تسجيلات)
        └─ 6. سجل الوصول   → check_in_log

كل ذلك في transaction واحدة — إما أن ينجح الكل أو يُلغى الكل.
التحليلات ولوحة المدير تقرأ من نفس الجداول، فتعكس الحدث تلقائياً.
"""
import logging
from datetime import date
from fastapi import APIRouter, Request, Depends, HTTPException

router = APIRouter(prefix="/api/integration", tags=["Integration"])
logger = logging.getLogger("dheuof")

# ── Lazy migration: revenue ledger + amenity-kit config ──────────────────────
_MIGRATION = """
CREATE TABLE IF NOT EXISTS revenue_transactions (
    id             SERIAL PRIMARY KEY,
    client_id      VARCHAR(50),
    booking_id     VARCHAR(50),
    category       VARCHAR(30) DEFAULT 'rooms',
    amount         DECIMAL(12,2) DEFAULT 0,
    payment_method VARCHAR(30) DEFAULT 'cash',
    description    TEXT,
    created_by     VARCHAR(100),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rev_client_date ON revenue_transactions(client_id, created_at);
CREATE TABLE IF NOT EXISTS amenity_kit (
    id              SERIAL PRIMARY KEY,
    client_id       VARCHAR(50),
    item_id         INTEGER REFERENCES warehouse_items(id) ON DELETE CASCADE,
    qty_per_checkin DECIMAL(10,2) DEFAULT 1,
    active          BOOLEAN DEFAULT TRUE,
    UNIQUE(client_id, item_id)
)
"""

_migration_done = False


def _ensure_tables(db) -> None:
    global _migration_done
    if _migration_done or not db.use_postgres:
        return
    failed = False
    for stmt in _MIGRATION.split(";"):
        s = stmt.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                if "already exists" not in str(e).lower():
                    logger.warning(f"integration migration: {e}")
                    failed = True
    # لا تُعلَّم منجزةً إلا إذا نجحت كلها.
    # كان العلَم يُرفع ولو فشلت الجمل، فلا يُعاد المحاولة أبداً طوال
    # عمر العملية: فشلٌ عابر عند أول استدعاء يُعطِّل التكامل كلّه حتى
    # إعادة التشغيل، وكل تسجيل دخول بعده يُرجع 500.
    if failed:
        logger.warning("ترحيل التكامل لم يكتمل — سيُعاد في الاستدعاء التالي")
        return
    _migration_done = True


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _recompute_today_kpi(cur, cid: str) -> dict:
    """Recompute today's daily_kpis snapshot inside the open transaction.

    Returns the fresh occupancy/revenue figures so the caller can echo the
    cascade back to the UI. Reads live from rooms + revenue_transactions.
    """
    today = date.today().isoformat()

    cur.execute("SELECT COUNT(*) AS c FROM rooms WHERE client_id=%s", (cid,))
    total_rooms = (cur.fetchone() or {}).get("c", 0) or 0

    cur.execute(
        "SELECT COUNT(*) AS c FROM rooms WHERE client_id=%s AND status='occupied'",
        (cid,),
    )
    occupied = (cur.fetchone() or {}).get("c", 0) or 0

    cur.execute(
        """SELECT COALESCE(SUM(amount),0) AS s FROM revenue_transactions
           WHERE client_id=%s AND created_at::date = CURRENT_DATE""",
        (cid,),
    )
    revenue_today = float((cur.fetchone() or {}).get("s", 0) or 0)

    cur.execute(
        """SELECT COUNT(*) AS c FROM check_in_log
           WHERE client_id=%s AND checked_in_at::date = CURRENT_DATE""",
        (cid,),
    )
    check_ins = (cur.fetchone() or {}).get("c", 0) or 0

    occ_rate = round((occupied / max(total_rooms, 1)) * 100, 2)
    adr = round(revenue_today / max(occupied, 1), 2)
    revpar = round(revenue_today / max(total_rooms, 1), 2)

    cur.execute(
        """
        INSERT INTO daily_kpis
            (client_id, kpi_date, total_rooms, occupied_rooms, occupancy_rate,
             adr, revpar, revenue_total, check_ins)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (client_id, kpi_date) DO UPDATE SET
            total_rooms    = EXCLUDED.total_rooms,
            occupied_rooms = EXCLUDED.occupied_rooms,
            occupancy_rate = EXCLUDED.occupancy_rate,
            adr            = EXCLUDED.adr,
            revpar         = EXCLUDED.revpar,
            revenue_total  = EXCLUDED.revenue_total,
            check_ins      = EXCLUDED.check_ins
        """,
        (cid, today, total_rooms, occupied, occ_rate, adr, revpar, revenue_today, check_ins),
    )

    return {
        "total_rooms": total_rooms,
        "occupied_rooms": occupied,
        "occupancy_rate": occ_rate,
        "revenue_today": revenue_today,
        "adr": adr,
        "revpar": revpar,
        "check_ins_today": check_ins,
    }


def _deduct_amenity_kit(cur, cid: str, by: str) -> list:
    """Deduct the configured amenity kit from inventory. Returns deducted items.

    Skips gracefully if no kit is configured. Never lets stock go below zero.
    """
    cur.execute(
        """
        SELECT k.item_id, k.qty_per_checkin, w.name, w.unit, w.quantity
        FROM amenity_kit k
        JOIN warehouse_items w ON w.id = k.item_id AND w.client_id = k.client_id
        WHERE k.client_id = %s AND k.active = TRUE
        """,
        (cid,),
    )
    kit = cur.fetchall() or []
    deducted = []
    for row in kit:
        r = dict(row)
        item_id = r["item_id"]
        qty = float(r["qty_per_checkin"] or 0)
        if qty <= 0:
            continue
        # Clamp so quantity never goes negative
        cur.execute(
            """
            UPDATE warehouse_items
            SET quantity = GREATEST(quantity - %s, 0)
            WHERE id = %s AND client_id = %s
            RETURNING quantity
            """,
            (qty, item_id, cid),
        )
        new_qty = (cur.fetchone() or {}).get("quantity", 0)
        cur.execute(
            """
            INSERT INTO warehouse_movements
                (item_id, client_id, movement_type, quantity, notes, created_by)
            VALUES (%s, %s, 'out', %s, %s, %s)
            """,
            (item_id, cid, qty, "صرف طقم ضيافة عند تسجيل الوصول", by),
        )
        deducted.append({
            "item_id": item_id,
            "name": r.get("name", ""),
            "unit": r.get("unit", ""),
            "deducted": qty,
            "remaining": float(new_qty),
        })
    return deducted


# ─────────────────────────────────────────────────────────────────────────────
#  Unified business event: check-in + payment cascade
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/checkin")
async def integrated_checkin(request: Request, session=Depends(_require_client)):
    """تسجيل وصول موحّد — يتسلسل عبر الغرف، المحاسبة، المخزون، KPI أتمياً.

    Body: { booking_id, amount?, payment_method?, checkin_by?, deduct_amenities? }
    """
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)

        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(400, "booking_id مطلوب")

        amount = float(data.get("amount", 0) or 0)
        payment_method = data.get("payment_method", "cash")
        by = data.get("checkin_by", session.get("client_id", "استقبال"))
        deduct_amenities = data.get("deduct_amenities", True)

        if not db.use_postgres:
            return {"success": True, "message": "وضع غير متصل — لم تُنفَّذ السلسلة"}

        cascade = {}
        with db.transaction() as cur:
            # 1. Booking → checked_in (only if currently confirmed)
            cur.execute(
                """
                UPDATE bookings SET status='checked_in', actual_check_in=NOW()
                WHERE id=%s AND client_id=%s AND status='confirmed'
                RETURNING room_id, guest_id, total_room, booking_number
                """,
                (booking_id, cid),
            )
            bk = cur.fetchone()
            if not bk:
                raise HTTPException(400, "الحجز غير موجود أو لا يمكن تسجيل وصوله (تحقق من الحالة)")
            bk = dict(bk)
            room_id = bk["room_id"]
            guest_id = bk["guest_id"]

            # 2. Room → occupied
            cur.execute(
                "UPDATE rooms SET status='occupied' WHERE id=%s AND client_id=%s RETURNING room_number",
                (room_id, cid),
            )
            room_row = cur.fetchone()
            room_number = dict(room_row).get("room_number", "") if room_row else ""
            cascade["room"] = {"room_number": room_number, "status": "occupied"}

            # 3. Accounting → revenue entry (only if a payment was made)
            if amount > 0:
                cur.execute(
                    """
                    INSERT INTO revenue_transactions
                        (client_id, booking_id, category, amount, payment_method, description, created_by)
                    VALUES (%s, %s, 'rooms', %s, %s, %s, %s)
                    """,
                    (cid, booking_id, amount, payment_method,
                     f"دفعة تسجيل وصول — حجز {bk.get('booking_number','')}", by),
                )
                cascade["accounting"] = {
                    "revenue_recorded": amount,
                    "payment_method": payment_method,
                }
            else:
                cascade["accounting"] = {"revenue_recorded": 0}

            # 4. Inventory → deduct amenity kit
            if deduct_amenities:
                cascade["inventory"] = {"deducted": _deduct_amenity_kit(cur, cid, by)}
            else:
                cascade["inventory"] = {"deducted": []}

            # 5. Check-in log
            cur.execute(
                """
                INSERT INTO check_in_log
                    (client_id, booking_id, room_id, guest_id, checkin_by, id_verified, key_issued)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (cid, booking_id, room_id, guest_id, by, True, True),
            )

            # 6. KPI snapshot → recompute today (occupancy/revenue/check-ins)
            cascade["kpi"] = _recompute_today_kpi(cur, cid)

        cascade["occupancy"] = {
            "occupied": cascade["kpi"]["occupied_rooms"],
            "total": cascade["kpi"]["total_rooms"],
            "rate": cascade["kpi"]["occupancy_rate"],
        }

        return {
            "success": True,
            "message": "تم تسجيل الوصول وتسلسل الحدث عبر جميع البرامج",
            "cascade": cascade,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in integrated_checkin: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/checkout")
async def integrated_checkout(request: Request, session=Depends(_require_client)):
    """مغادرة موحّدة — الغرفة للتنظيف + قيد الدفعة النهائية + تحديث KPI."""
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)

        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(400, "booking_id مطلوب")

        final_amount = float(data.get("final_amount", 0) or 0)
        payment_method = data.get("payment_method", "cash")
        by = data.get("checkout_by", session.get("client_id", "استقبال"))

        if not db.use_postgres:
            return {"success": True, "message": "وضع غير متصل"}

        cascade = {}
        with db.transaction() as cur:
            cur.execute(
                """
                UPDATE bookings SET status='checked_out', actual_check_out=NOW()
                WHERE id=%s AND client_id=%s AND status='checked_in'
                RETURNING room_id, booking_number
                """,
                (booking_id, cid),
            )
            bk = cur.fetchone()
            if not bk:
                raise HTTPException(400, "الحجز غير موجود أو الضيف لم يُسجَّل وصوله")
            bk = dict(bk)
            room_id = bk["room_id"]

            cur.execute(
                "UPDATE rooms SET status='cleaning' WHERE id=%s AND client_id=%s RETURNING room_number",
                (room_id, cid),
            )
            room_row = cur.fetchone()
            cascade["room"] = {
                "room_number": dict(room_row).get("room_number", "") if room_row else "",
                "status": "cleaning",
            }

            if final_amount > 0:
                cur.execute(
                    """
                    INSERT INTO revenue_transactions
                        (client_id, booking_id, category, amount, payment_method, description, created_by)
                    VALUES (%s, %s, 'rooms', %s, %s, %s, %s)
                    """,
                    (cid, booking_id, final_amount, payment_method,
                     f"دفعة مغادرة — حجز {bk.get('booking_number','')}", by),
                )
            cascade["accounting"] = {"final_amount": final_amount, "payment_method": payment_method}

            cur.execute(
                """
                INSERT INTO check_out_log
                    (client_id, booking_id, checkout_by, final_amount, payment_method)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (cid, booking_id, by, final_amount, payment_method),
            )

            cascade["kpi"] = _recompute_today_kpi(cur, cid)

        cascade["housekeeping"] = {"task": "الغرفة بحاجة لتنظيف", "auto_created": True}
        return {
            "success": True,
            "message": "تمت المغادرة وتسلسل الحدث عبر البرامج",
            "cascade": cascade,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in integrated_checkout: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─────────────────────────────────────────────────────────────────────────────
#  Maintenance: close ticket → deduct used parts from warehouse (automated)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/maintenance/close")
async def close_maintenance_order(request: Request, session=Depends(_require_client)):
    """إغلاق تذكرة صيانة + خصم قطع الغيار المستخدمة من المستودع — تدفق أتمي.

    Body: {
        order_id,                              # رقم تذكرة الصيانة
        parts: [{ item_id, qty }],             # القطع المستخدمة (تُخصم من المستودع)
        actual_cost?,                          # التكلفة الفعلية (تشمل العمالة)
        notes?,
        free_room?                             # إعادة الغرفة إلى 'available' بعد الإصلاح
    }
    """
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)

        order_id = data.get("order_id")
        if not order_id:
            raise HTTPException(400, "order_id مطلوب")

        parts = data.get("parts", []) or []
        notes = data.get("notes", "")
        free_room = bool(data.get("free_room", False))
        by = data.get("closed_by", session.get("client_id", "الصيانة"))

        if not db.use_postgres:
            return {"success": True, "message": "وضع غير متصل"}

        cascade = {}
        with db.transaction() as cur:
            # 1. Close the maintenance order
            cur.execute(
                """
                UPDATE maintenance_orders
                SET status='completed', completed_at=NOW(), actual_cost=%s, notes=%s
                WHERE id=%s AND client_id=%s AND status IN ('open','in_progress')
                RETURNING order_number, room_id, actual_cost
                """,
                (float(data.get("actual_cost", 0) or 0), notes, order_id, cid),
            )
            order = cur.fetchone()
            if not order:
                raise HTTPException(400, "تذكرة الصيانة غير موجودة أو مغلقة مسبقاً")
            order = dict(order)
            cascade["maintenance"] = {
                "order_number": order.get("order_number", ""),
                "status": "completed",
            }

            # 2. Deduct each used part from the warehouse (maintenance parts)
            deducted = []
            parts_cost = 0.0
            for p in parts:
                item_id = p.get("item_id")
                qty = float(p.get("qty", 0) or 0)
                if not item_id or qty <= 0:
                    continue
                cur.execute(
                    """
                    UPDATE warehouse_items
                    SET quantity = GREATEST(quantity - %s, 0)
                    WHERE id=%s AND client_id=%s
                    RETURNING name, unit, quantity, price_per_unit
                    """,
                    (qty, int(item_id), cid),
                )
                wi = cur.fetchone()
                if not wi:
                    continue
                wi = dict(wi)
                line_cost = qty * float(wi.get("price_per_unit", 0) or 0)
                parts_cost += line_cost
                cur.execute(
                    """
                    INSERT INTO warehouse_movements
                        (item_id, client_id, movement_type, quantity, notes, created_by)
                    VALUES (%s, %s, 'out', %s, %s, %s)
                    """,
                    (int(item_id), cid, qty,
                     f"صرف قطع صيانة — تذكرة {order.get('order_number','')}", by),
                )
                deducted.append({
                    "item_id": item_id,
                    "name": wi.get("name", ""),
                    "unit": wi.get("unit", ""),
                    "deducted": qty,
                    "remaining": float(wi.get("quantity", 0)),
                    "line_cost": round(line_cost, 2),
                })
            cascade["warehouse"] = {"parts_deducted": deducted, "parts_cost": round(parts_cost, 2)}

            # 3. Optionally return the room to service
            if free_room and order.get("room_id"):
                cur.execute(
                    "UPDATE rooms SET status='available' WHERE id=%s AND client_id=%s AND status='maintenance'",
                    (order["room_id"], cid),
                )
                cascade["room"] = {"room_id": order["room_id"], "status": "available"}

        return {
            "success": True,
            "message": "تم إغلاق تذكرة الصيانة وخصم القطع من المستودع تلقائياً",
            "cascade": cascade,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in close_maintenance_order: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─────────────────────────────────────────────────────────────────────────────
#  Amenity-kit configuration (what to deduct on each check-in)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/amenity-kit")
async def get_amenity_kit(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)
        if db.use_postgres:
            rows = db.execute(
                """
                SELECT k.id, k.item_id, k.qty_per_checkin, k.active,
                       w.name, w.unit, w.quantity AS in_stock
                FROM amenity_kit k
                JOIN warehouse_items w ON w.id = k.item_id
                WHERE k.client_id = %s
                ORDER BY w.name
                """,
                (cid,), fetch="all",
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_amenity_kit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/amenity-kit")
async def set_amenity_kit_item(request: Request, session=Depends(_require_client)):
    """أضف/حدّث صنفاً في طقم الضيافة: { item_id, qty_per_checkin, active? }"""
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)
        item_id = data.get("item_id")
        if not item_id:
            raise HTTPException(400, "item_id مطلوب")
        qty = float(data.get("qty_per_checkin", 1) or 1)
        active = bool(data.get("active", True))
        if db.use_postgres:
            db.execute(
                """
                INSERT INTO amenity_kit (client_id, item_id, qty_per_checkin, active)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (client_id, item_id) DO UPDATE SET
                    qty_per_checkin = EXCLUDED.qty_per_checkin,
                    active          = EXCLUDED.active
                """,
                (cid, int(item_id), qty, active),
            )
        return {"success": True, "message": "تم تحديث طقم الضيافة"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in set_amenity_kit_item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.delete("/amenity-kit/{item_id}")
async def remove_amenity_kit_item(item_id: int, request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)
        if db.use_postgres:
            db.execute(
                "DELETE FROM amenity_kit WHERE client_id=%s AND item_id=%s",
                (cid, item_id),
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in remove_amenity_kit_item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ─────────────────────────────────────────────────────────────────────────────
#  Unified live dashboard — shows the interconnection at a glance
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def integration_dashboard(request: Request, session=Depends(_require_client)):
    """لقطة حية موحّدة تُظهر ترابط البرامج: إشغال + إيراد + مخزون منخفض + KPI."""
    try:
        import asyncio
        db = request.app.state.db
        cid = session["client_id"]
        _ensure_tables(db)
        if not db.use_postgres:
            return {"success": True, "data": {}}

        async def q(sql, label):
            try:
                return await db.async_execute(sql, (cid,), fetch="one")
            except Exception as e:
                logger.warning(f"dashboard {label}: {e}")
                return None

        rooms_r, revenue_r, kpi_r, low_stock_r = await asyncio.gather(
            q("SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status='occupied') AS occupied, "
              "COUNT(*) FILTER (WHERE status='cleaning') AS cleaning, "
              "COUNT(*) FILTER (WHERE status='available') AS available FROM rooms WHERE client_id=%s", "rooms"),
            q("SELECT COALESCE(SUM(amount),0) AS today FROM revenue_transactions "
              "WHERE client_id=%s AND created_at::date = CURRENT_DATE", "revenue"),
            q("SELECT occupancy_rate, adr, revpar, revenue_total, check_ins FROM daily_kpis "
              "WHERE client_id=%s AND kpi_date = CURRENT_DATE", "kpi"),
            q("SELECT COUNT(*) AS c FROM warehouse_items WHERE client_id=%s "
              "AND reorder_level > 0 AND quantity <= reorder_level", "low_stock"),
        )

        rooms = dict(rooms_r) if rooms_r else {}
        total = rooms.get("total", 0) or 0
        occupied = rooms.get("occupied", 0) or 0
        return {
            "success": True,
            "data": {
                "occupancy": {
                    "total": total,
                    "occupied": occupied,
                    "cleaning": rooms.get("cleaning", 0),
                    "available": rooms.get("available", 0),
                    "rate": round((occupied / max(total, 1)) * 100, 1),
                },
                "revenue_today": float(dict(revenue_r).get("today", 0)) if revenue_r else 0.0,
                "kpi": dict(kpi_r) if kpi_r else {},
                "low_stock_alerts": dict(low_stock_r).get("c", 0) if low_stock_r else 0,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in integration_dashboard: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
