#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M06 Accounting — المحاسبة والفواتير + API مفتوح للربط بالأنظمة الخارجية"""
import json
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from fastapi.responses import Response
from db.connection import count_of

router = APIRouter(prefix="/api/m06acc", tags=["Accounting"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


# ── Company tax profile — all fields OPTIONAL ────────────────────────────────
_TAX_FIELDS = ("vat_number", "cr_number", "national_address", "company_name")


@router.get("/company-profile")
async def get_company_profile(request: Request, session=Depends(_require_client)):
    """يُعيد بيانات المنشأة الضريبية (اختيارية) المخزّنة في invoice_settings."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        profile = {k: "" for k in _TAX_FIELDS}
        if db.use_postgres:
            row = db.execute(
                "SELECT invoice_settings FROM clients WHERE id=%s", (cid,), fetch="one")
            if row:
                settings = dict(row).get("invoice_settings") or {}
                if isinstance(settings, str):
                    try:
                        settings = json.loads(settings)
                    except Exception:
                        settings = {}
                for k in _TAX_FIELDS:
                    profile[k] = settings.get(k, "")
        return {"success": True, "data": profile}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_company_profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/company-profile")
async def set_company_profile(request: Request, session=Depends(_require_client)):
    """يحفظ بيانات المنشأة الضريبية — كل الحقول اختيارية، يُدمج مع الموجود.

    Body (كله اختياري): { vat_number?, cr_number?, national_address?, company_name? }
    """
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute(
                "SELECT invoice_settings FROM clients WHERE id=%s", (cid,), fetch="one")
            settings = {}
            if row:
                existing = dict(row).get("invoice_settings") or {}
                if isinstance(existing, str):
                    try:
                        existing = json.loads(existing)
                    except Exception:
                        existing = {}
                settings = dict(existing)
            for k in _TAX_FIELDS:
                if k in data:
                    settings[k] = (data.get(k) or "").strip()
            db.execute(
                "UPDATE clients SET invoice_settings=%s, updated_at=NOW() WHERE id=%s",
                (json.dumps(settings, ensure_ascii=False), cid))
        return {"success": True, "message": "تم حفظ بيانات المنشأة الضريبية"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in set_company_profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ── Tax Configuration ─────────────────────────────────────────────────────────

@router.get("/tax-config")
async def get_tax_config(request: Request, session=Depends(_require_client)):
    """يُعيد إعدادات الضريبة الحالية للمنشأة.

    الوضعان:
      MODE_A — الضريبة تُضاف فوق المجموع (الافتراضي)
      MODE_B — الضريبة مُضمَّنة في المجموع الكلي (استخراج 15% + 2.5% = 82.5% صافي)
    """
    try:
        from services.tax_config import get_client_tax_config
        db = request.app.state.db
        cid = session["client_id"]
        cfg = get_client_tax_config(db, cid)
        return {
            "success": True,
            "data": {
                "tax_mode":        cfg.mode,
                "vat_rate":        float(cfg.vat_rate),
                "tourism_rate":    float(cfg.tourism_rate),
                "tourism_enabled": cfg.tourism_enabled,
            },
            "description": {
                "MODE_A": "الضريبة تُضاف: المجموع + VAT + سياحة = الكلي",
                "MODE_B": "الضريبة مُضمَّنة: الكلي = 100%، صافي = 82.5%، VAT = 15%، سياحة = 2.5%",
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_tax_config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/tax-config")
async def set_tax_config(request: Request, session=Depends(_require_client)):
    """يحفظ إعدادات الضريبة — يُدمج مع invoice_settings الموجودة.

    Body (كله اختياري):
      { tax_mode?: "MODE_A"|"MODE_B",
        vat_rate?: 0.15,
        tourism_rate?: 0.025,
        tourism_enabled?: true }
    """
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute(
                "SELECT invoice_settings FROM clients WHERE id=%s", (cid,), fetch="one")
            settings = {}
            if row:
                existing = dict(row).get("invoice_settings") or {}
                if isinstance(existing, str):
                    try:
                        existing = json.loads(existing)
                    except Exception:
                        existing = {}
                settings = dict(existing)
            if "tax_mode" in data:
                if data["tax_mode"] not in ("MODE_A", "MODE_B"):
                    raise HTTPException(400, "tax_mode يجب أن يكون MODE_A أو MODE_B")
                settings["tax_mode"] = data["tax_mode"]
            if "vat_rate" in data:
                settings["vat_rate"] = float(data["vat_rate"])
            if "tourism_rate" in data:
                settings["tourism_rate"] = float(data["tourism_rate"])
            if "tourism_enabled" in data:
                settings["tourism_enabled"] = bool(data["tourism_enabled"])
            db.execute(
                "UPDATE clients SET invoice_settings=%s, updated_at=NOW() WHERE id=%s",
                (json.dumps(settings, ensure_ascii=False), cid))
        return {"success": True, "message": "تم حفظ إعدادات الضريبة"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in set_tax_config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ── Invoices ──────────────────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    per_page: int = 50,
    session=Depends(_require_client),
):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            limit = min(per_page, 200)
            offset = (page - 1) * limit
            q = """
                SELECT
                    b.id,
                    b.booking_number,
                    COALESCE(g.full_name, '') AS guest_name,
                    r.room_number,
                    b.check_in,
                    b.check_out,
                    b.total_room                                AS grand_total,
                    COALESCE(b.vat_amount, 0)                  AS vat_amount,
                    COALESCE(b.tourism_tax_amount, 0)          AS tourism_tax_amount,
                    COALESCE(b.tax_mode, 'MODE_A')             AS tax_mode,
                    b.total_room
                        - COALESCE(b.vat_amount, 0)
                        - COALESCE(b.tourism_tax_amount, 0)    AS net_amount,
                    b.status,
                    b.created_at
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
                  AND b.status IN ('checked_out', 'confirmed')
            """
            params = [cid]
            if date_from:
                q += " AND b.check_in >= %s"
                params.append(date_from)
            if date_to:
                q += " AND b.check_in <= %s"
                params.append(date_to)
            count_q = f"SELECT COUNT(*) FROM ({q}) AS _sub"
            count_result = db.execute(count_q, params, fetch="one")
            total = count_of(count_result)
            q += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])], "page": page, "per_page": limit, "total": total}
        return {"success": True, "data": [], "page": page, "per_page": per_page, "total": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_invoices: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/revenue/summary")
async def revenue_summary(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute(
                """
                SELECT
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in::date = CURRENT_DATE
                    ), 0) AS today,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in >= date_trunc('week', CURRENT_DATE)
                    ), 0) AS this_week,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in >= date_trunc('month', CURRENT_DATE)
                    ), 0) AS this_month,
                    COALESCE(SUM(total_room) FILTER (
                        WHERE check_in >= date_trunc('month', CURRENT_DATE) - INTERVAL '1 month'
                          AND check_in <  date_trunc('month', CURRENT_DATE)
                    ), 0) AS last_month,
                    COALESCE(SUM(COALESCE(vat_amount, 0)) FILTER (
                        WHERE check_in >= date_trunc('month', CURRENT_DATE)
                    ), 0) AS this_month_vat,
                    COALESCE(SUM(COALESCE(tourism_tax_amount, 0)) FILTER (
                        WHERE check_in >= date_trunc('month', CURRENT_DATE)
                    ), 0) AS this_month_tourism_tax
                FROM bookings
                WHERE client_id = %s
                  AND status IN ('checked_out', 'confirmed')
                """,
                (cid,),
                fetch="one",
            )
            return {"success": True, "data": dict(row) if row else {
                "today": 0, "this_week": 0, "this_month": 0, "last_month": 0,
                "this_month_vat": 0, "this_month_tourism_tax": 0,
            }}
        return {"success": True, "data": {
            "today": 0, "this_week": 0, "this_month": 0, "last_month": 0,
            "this_month_vat": 0, "this_month_tourism_tax": 0,
        }}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revenue_summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/revenue/by-month")
async def revenue_by_month(request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                """
                SELECT
                    TO_CHAR(date_trunc('month', check_in), 'YYYY-MM') AS month,
                    COALESCE(SUM(total_room), 0)                       AS revenue,
                    COALESCE(SUM(COALESCE(vat_amount, 0)), 0)          AS vat_total,
                    COALESCE(SUM(COALESCE(tourism_tax_amount, 0)), 0)  AS tourism_total,
                    COALESCE(SUM(
                        total_room
                        - COALESCE(vat_amount, 0)
                        - COALESCE(tourism_tax_amount, 0)
                    ), 0) AS net_revenue,
                    COUNT(*)                                            AS bookings_count
                FROM bookings
                WHERE client_id = %s
                  AND status IN ('checked_out', 'confirmed')
                  AND check_in >= CURRENT_DATE - INTERVAL '12 months'
                GROUP BY date_trunc('month', check_in)
                ORDER BY date_trunc('month', check_in)
                """,
                (cid,),
                fetch="all",
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in revenue_by_month: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/export")
async def export_ledger(
    request: Request,
    format: str = "csv",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    session=Depends(_require_client),
):
    """دفتر أستاذٍ موحّد (دفعات + قيود) مربوطٌ بمصدره — CSV أو JSON.

    كلّ استعلامٍ معزولٌ بالمنشأة؛ نطاق التاريخ اختياري.
    """
    from services import accounting_export
    db = request.app.state.db
    cid = session["client_id"]
    payments, journals = [], []
    if getattr(db, "use_postgres", False):
        pq = "SELECT amount, method, reference, device_id, currency, created_at FROM payments WHERE client_id=%s"
        pp = [cid]
        if date_from:
            pq += " AND created_at::date >= %s::date"; pp.append(date_from)  # noqa: E702
        if date_to:
            pq += " AND created_at::date <= %s::date"; pp.append(date_to)  # noqa: E702
        pq += " ORDER BY created_at DESC LIMIT 5000"
        payments = [dict(r) for r in (db.execute(pq, tuple(pp), fetch="all") or [])]

        jq = "SELECT reference, entry_date, description, lines, source, created_at FROM journal_entries WHERE client_id=%s"
        jp = [cid]
        if date_from:
            jq += " AND entry_date >= %s::date"; jp.append(date_from)  # noqa: E702
        if date_to:
            jq += " AND entry_date <= %s::date"; jp.append(date_to)  # noqa: E702
        jq += " ORDER BY entry_date DESC LIMIT 5000"
        journals = [dict(r) for r in (db.execute(jq, tuple(jp), fetch="all") or [])]

    rows = accounting_export.build_ledger(payments, journals)
    if format == "json":
        return {"success": True, "data": accounting_export.to_json(rows)}
    csv_text = accounting_export.to_csv(rows)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=ledger.csv"},
    )


@router.get("/outstanding")
async def list_outstanding(request: Request, session=Depends(_require_client)):
    """Bookings that are confirmed but check-out date has passed (overdue checkout)."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            rows = db.execute(
                """
                SELECT
                    b.id,
                    b.booking_number,
                    COALESCE(g.full_name, '') AS guest_name,
                    r.room_number,
                    b.check_in,
                    b.check_out,
                    b.total_room,
                    COALESCE(b.vat_amount, 0)         AS vat_amount,
                    COALESCE(b.tourism_tax_amount, 0) AS tourism_tax_amount,
                    b.status,
                    b.created_at
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
                  AND b.status = 'confirmed'
                  AND b.check_out < NOW()
                ORDER BY b.check_out ASC
                LIMIT 100
                """,
                (cid,),
                fetch="all",
            )
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_outstanding: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/payment")
async def record_payment(request: Request, session=Depends(_require_client)):
    """Record a payment against a booking: update status and append notes."""
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]

        booking_id = data.get("booking_id")
        if not booking_id:
            raise HTTPException(status_code=400, detail="booking_id مطلوب")

        new_status = data.get("status", "checked_out")
        notes = data.get("notes", "")
        payment_method = data.get("payment_method", "cash")
        amount = float(data.get("amount", 0) or 0)

        if db.use_postgres:
            db.execute(
                """
                UPDATE bookings
                SET status = %s,
                    notes  = COALESCE(NULLIF(notes,''), '') || %s
                WHERE id = %s AND client_id = %s
                """,
                (
                    new_status,
                    f"\n[دفعة] {payment_method}: {amount} — {notes}".strip(),
                    booking_id,
                    cid,
                ),
            )
            if new_status == "checked_out":
                db.execute(
                    """
                    INSERT INTO check_out_log
                        (client_id, booking_id, checkout_by, final_amount, payment_method, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        cid,
                        str(booking_id),
                        session.get("client_id", ""),
                        amount,
                        payment_method,
                        notes,
                    ),
                )
            return {"success": True, "message": "تم تسجيل الدفعة بنجاح"}
        return {"success": True, "message": "تم التسجيل (وضع غير متصل)"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in record_payment: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ── مفتاح API للربط بالأنظمة الخارجية ───────────────────────────────────────

@router.get("/api-key")
async def get_api_key(request: Request, session=Depends(_require_client)):
    """يُعيد مفتاح API الحالي للمنشأة (أو يُنشئ واحداً جديداً)."""
    try:
        import secrets as _secrets
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("SELECT api_key FROM clients WHERE id=%s", (cid,), fetch="one")
            key = dict(row).get("api_key") if row else None
            if not key:
                key = "sk_" + _secrets.token_hex(32)
                db.execute("UPDATE clients SET api_key=%s WHERE id=%s", (key, cid))
            return {"success": True, "data": {"api_key": key}}
        return {"success": False, "message": "يتطلب قاعدة بيانات"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_api_key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/api-key/rotate")
async def rotate_api_key(request: Request, session=Depends(_require_client)):
    """يُولّد مفتاح API جديداً (يُبطل القديم فوراً)."""
    try:
        import secrets as _secrets
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            new_key = "sk_" + _secrets.token_hex(32)
            db.execute("UPDATE clients SET api_key=%s WHERE id=%s", (new_key, cid))
            return {"success": True, "data": {"api_key": new_key}, "message": "تم تحديث المفتاح — احفظه فوراً لأنه لن يظهر مرة أخرى"}
        return {"success": False, "message": "يتطلب قاعدة بيانات"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in rotate_api_key: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ── Open Accounting API — للربط بالأنظمة المحاسبية الخارجية ──────────────────
# المصادقة: X-API-Key header (مفتاح API من إعدادات المنشأة)

def _get_client_by_api_key(db, api_key: str) -> Optional[str]:
    """يُعيد client_id إذا كان المفتاح صحيحاً، وإلا None."""
    if not api_key or not db.use_postgres:
        return None
    try:
        row = db.execute(
            "SELECT id FROM clients WHERE api_key=%s AND is_active=TRUE LIMIT 1",
            (api_key,), fetch="one",
        )
        return dict(row)["id"] if row else None
    except Exception:
        return None


@router.get("/open/transactions")
async def open_list_transactions(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    page: int = 1,
    per_page: int = 100,
    x_api_key: Optional[str] = Header(None),
):
    """
    [API مفتوح] قائمة المعاملات المالية مع تفاصيل الضريبة.

    المصادقة: Header   X-API-Key: <مفتاح API المنشأة>

    الاستخدام مع برامج المحاسبة الخارجية (Odoo, SAP, QuickBooks ...):
      GET /api/m06acc/open/transactions
          ?date_from=2025-01-01&date_to=2025-01-31
          &X-API-Key: sk_...

    يُعيد لكل معاملة:
      id, booking_number, guest_name, check_in, check_out,
      grand_total, net_amount, vat_amount, tourism_tax_amount,
      tax_mode, status, source, created_at
    """
    db = request.app.state.db
    cid = _get_client_by_api_key(db, x_api_key)
    if not cid:
        raise HTTPException(401, "X-API-Key غير صالح أو مفقود")

    try:
        limit = min(per_page, 500)
        offset = (page - 1) * limit
        if db.use_postgres:
            q = """
                SELECT
                    b.id,
                    b.booking_number,
                    COALESCE(g.full_name, '')          AS guest_name,
                    r.room_number,
                    b.check_in,
                    b.check_out,
                    b.total_room                               AS grand_total,
                    COALESCE(b.vat_amount, 0)                  AS vat_amount,
                    COALESCE(b.tourism_tax_amount, 0)          AS tourism_tax_amount,
                    COALESCE(b.tax_mode, 'MODE_A')             AS tax_mode,
                    b.total_room
                        - COALESCE(b.vat_amount, 0)
                        - COALESCE(b.tourism_tax_amount, 0)    AS net_amount,
                    b.status,
                    b.source,
                    b.created_at
                FROM bookings b
                LEFT JOIN guests g ON b.guest_id = g.id
                LEFT JOIN rooms  r ON b.room_id  = r.id
                WHERE b.client_id = %s
                  AND b.status IN ('checked_out', 'confirmed', 'checked_in')
            """
            params: list = [cid]
            if date_from:
                q += " AND b.check_in >= %s"
                params.append(date_from)
            if date_to:
                q += " AND b.check_in <= %s"
                params.append(date_to)
            if source:
                q += " AND b.source = %s"
                params.append(source)
            count_row = db.execute(f"SELECT COUNT(*) FROM ({q}) AS _s", params, fetch="one")
            total = count_of(count_row)
            q += " ORDER BY b.created_at DESC LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            rows = db.execute(q, params, fetch="all")
            return {
                "success": True,
                "data": [dict(r) for r in (rows or [])],
                "meta": {"page": page, "per_page": limit, "total": total},
            }
        return {"success": True, "data": [], "meta": {"page": page, "per_page": limit, "total": 0}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"open_list_transactions: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.get("/open/tax-summary")
async def open_tax_summary(
    request: Request,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    x_api_key: Optional[str] = Header(None),
):
    """
    [API مفتوح] ملخص الضرائب لفترة زمنية.

    يُعيد: إجمالي الإيرادات، إجمالي VAT، إجمالي ضريبة السياحة، صافي الإيراد.
    مفيد لملف الإقرار الضريبي الربعي (ZATCA).
    """
    db = request.app.state.db
    cid = _get_client_by_api_key(db, x_api_key)
    if not cid:
        raise HTTPException(401, "X-API-Key غير صالح أو مفقود")

    try:
        if db.use_postgres:
            q = """
                SELECT
                    COUNT(*)                                          AS transactions,
                    COALESCE(SUM(total_room), 0)                     AS total_revenue,
                    COALESCE(SUM(COALESCE(vat_amount, 0)), 0)        AS total_vat,
                    COALESCE(SUM(COALESCE(tourism_tax_amount, 0)), 0) AS total_tourism_tax,
                    COALESCE(SUM(
                        total_room
                        - COALESCE(vat_amount, 0)
                        - COALESCE(tourism_tax_amount, 0)
                    ), 0) AS total_net
                FROM bookings
                WHERE client_id = %s
                  AND status IN ('checked_out', 'confirmed')
            """
            params: list = [cid]
            if date_from:
                q += " AND check_in >= %s"
                params.append(date_from)
            if date_to:
                q += " AND check_in <= %s"
                params.append(date_to)
            row = db.execute(q, params, fetch="one")
            return {"success": True, "data": dict(row) if row else {}}
        return {"success": True, "data": {}}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"open_tax_summary: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/open/journal-entry")
async def open_post_journal_entry(
    request: Request,
    x_api_key: Optional[str] = Header(None),
):
    """
    [API مفتوح] استقبال قيد محاسبي من نظام خارجي.

    Body:
      {
        "reference":    "INV-2025-001",
        "entry_date":   "2025-01-15",
        "description":  "إيراد إقامة",
        "lines": [
          {"account": "إيرادات الإقامة", "debit": 0,   "credit": 900.00},
          {"account": "ضريبة القيمة المضافة", "debit": 0, "credit": 135.00},
          {"account": "ضريبة السياحة",    "debit": 0,   "credit": 22.50},
          {"account": "الذمم المدينة",    "debit": 1057.50, "credit": 0}
        ]
      }

    يُخزَّن في journal_entries (جدول يُنشأ تلقائياً عند الحاجة).
    """
    db = request.app.state.db
    cid = _get_client_by_api_key(db, x_api_key)
    if not cid:
        raise HTTPException(401, "X-API-Key غير صالح أو مفقود")

    try:
        data = await request.json()
        if db.use_postgres:
            # إنشاء جدول journal_entries إذا لم يكن موجوداً
            db.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id          SERIAL PRIMARY KEY,
                    client_id   VARCHAR(50) REFERENCES clients(id) ON DELETE CASCADE,
                    reference   VARCHAR(100),
                    entry_date  DATE DEFAULT CURRENT_DATE,
                    description TEXT,
                    lines       JSONB DEFAULT '[]',
                    source      VARCHAR(30) DEFAULT 'external',
                    created_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            row = db.execute("""
                INSERT INTO journal_entries
                    (client_id, reference, entry_date, description, lines, source)
                VALUES (%s, %s, %s::date, %s, %s::jsonb, 'external')
                RETURNING id
            """, (
                cid,
                data.get("reference", ""),
                data.get("entry_date"),
                data.get("description", ""),
                json.dumps(data.get("lines", []), ensure_ascii=False),
            ), fetch="one")
            entry_id = dict(row)["id"] if row else None
            return {"success": True, "data": {"id": entry_id}, "message": "تم استقبال القيد المحاسبي"}
        return {"success": True, "message": "تم الاستقبال (وضع غير متصل)"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"open_post_journal_entry: {e}", exc_info=True)
        raise HTTPException(500, str(e))
