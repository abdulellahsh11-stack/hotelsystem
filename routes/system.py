#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
routes/system.py — الصحة والحالة والنسخ الاحتياطي والتحليل الذكي
مُستخرَج ضمن تقسيم ملف المسارات الكبير لتسهيل الصيانة.
"""
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app_core import (
    log, _lock, _client_sessions,
    require_client,
)

router = APIRouter()

# ──────────────────────────────────────────────────────────────
#  Health & Status
# ──────────────────────────────────────────────────────────────
@router.get("/api/health")
async def health(request: Request):
    db = getattr(request.app.state, "db", None)
    db_ok = False
    try:
        if db:
            result = db.health()
            db_ok = bool(result and result.get("ok"))
    except Exception:
        pass
    return {
        "ok": True,
        "status": "healthy",
        "db": "connected" if db_ok else "unavailable",
        "time": datetime.now().isoformat(),
        "version": "3.1.0",
    }


@router.get("/api/status")
async def status(request: Request):
    db = request.app.state.db
    sessions_count = 0
    try:
        with _lock:
            sessions_count = len(_client_sessions)
    except Exception:
        pass
    return {
        "ok": True,
        "version": "3.0.0",
        "db": db.health(),
        "active_sessions": sessions_count,
        "time": datetime.now().isoformat(),
    }


@router.get("/api/analytics/overview")
async def analytics_overview(request: Request, session=Depends(require_client)):
    """Aggregated cross-module overview for the analytics dashboard (M12)."""
    try:
        db = request.app.state.db
        cid = session["client_id"]
        result = {
            "employees": {"total": 0, "active": 0},
            "bookings": {"this_month": 0, "revenue_this_month": 0, "occupancy_rate": 0},
            "inventory": {"total_items": 0, "low_stock": 0, "total_value": 0},
            "maintenance": {"open_orders": 0, "in_progress": 0},
            "tours": {"total_tours": 0, "bookings_this_month": 0},
        }
        if not db.use_postgres:
            return {"success": True, "data": result}

        # Employees
        row = db.execute(
            "SELECT COUNT(*) as total, COUNT(*) FILTER(WHERE status='active') as active FROM employees WHERE client_id=%s",
            (cid,), fetch="one"
        )
        if row:
            result["employees"] = {"total": row["total"] or 0, "active": row["active"] or 0}

        # Bookings this month
        row = db.execute(
            """SELECT COUNT(*) as cnt,
                      COALESCE(SUM(total_room), 0) as revenue,
                      ROUND(COUNT(*) FILTER(WHERE status IN ('confirmed','checked_in')) * 100.0 / NULLIF(COUNT(*), 0), 1) as occ
               FROM bookings
               WHERE client_id=%s
                 AND DATE_TRUNC('month', check_in) = DATE_TRUNC('month', NOW())""",
            (cid,), fetch="one"
        )
        if row:
            result["bookings"] = {
                "this_month": row["cnt"] or 0,
                "revenue_this_month": float(row["revenue"] or 0),
                "occupancy_rate": float(row["occ"] or 0),
            }

        # Inventory
        row = db.execute(
            """SELECT COUNT(*) as total,
                      COUNT(*) FILTER(WHERE quantity <= reorder_level AND reorder_level > 0) as low_stock,
                      COALESCE(SUM(quantity * price_per_unit), 0) as total_value
               FROM warehouse_items WHERE client_id=%s""",
            (cid,), fetch="one"
        )
        if row:
            result["inventory"] = {
                "total_items": row["total"] or 0,
                "low_stock": row["low_stock"] or 0,
                "total_value": float(row["total_value"] or 0),
            }

        # Maintenance
        row = db.execute(
            """SELECT COUNT(*) FILTER(WHERE status='open') as open_cnt,
                      COUNT(*) FILTER(WHERE status='in_progress') as in_progress
               FROM maintenance_orders WHERE client_id=%s""",
            (cid,), fetch="one"
        )
        if row:
            result["maintenance"] = {
                "open_orders": row["open_cnt"] or 0,
                "in_progress": row["in_progress"] or 0,
            }

        # Tours
        row = db.execute(
            """SELECT COUNT(DISTINCT tc.id) as total_tours,
                      COUNT(tb.id) FILTER(WHERE DATE_TRUNC('month', tb.created_at) = DATE_TRUNC('month', NOW())) as monthly_bookings
               FROM tour_catalog tc
               LEFT JOIN tour_bookings tb ON tc.id = tb.tour_id AND tb.client_id=%s
               WHERE tc.client_id=%s""",
            (cid, cid), fetch="one"
        )
        if row:
            result["tours"] = {
                "total_tours": row["total_tours"] or 0,
                "bookings_this_month": row["monthly_bookings"] or 0,
            }

        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"analytics_overview error: {e}", exc_info=True)
        raise HTTPException(500, f"خطأ في التحليلات: {str(e)}")


# ──────────────────────────────────────────────────────────────
#  Backup
# ──────────────────────────────────────────────────────────────
def _require_backup_access(session: dict) -> None:
    """
    سياسة الوصول للنسخ الاحتياطي.

    النسخة تحوي بيانات المنشأة كاملةً — نزلاء وأرقام هوية ورواتب — فلا
    تُفتح لكل موظف مسجَّل. صاحب المنشأة والمدير العام يمرّان دائماً،
    وغيرهما يحتاج صلاحية `backup` صريحة.

    عند غياب نظام أدوار الموظفين تكون الجلسة جلسةَ مالك المنشأة، فيمرّ
    عبر الدور `owner` — أي أن السياسة تعمل اليوم وتتشدّد تلقائياً حين
    تُضاف حسابات الموظفين.
    """
    from db.security import enforce_permission

    try:
        enforce_permission(session, "backup")
    except PermissionError as exc:
        # enforce_permission يرمي PermissionError وهو ليس HTTPException،
        # فبدون هذا التحويل يتحوّل رفضُ الصلاحية إلى خطأ خادم 500.
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/api/backup/create")
async def backup_create(request: Request, session=Depends(require_client)):
    """يُنشئ نسخة شهرية مضغوطة للمنشأة الحالية ويعيد بيانها."""
    from services.backup_archive import archive_filename, build_archive

    _require_backup_access(session)
    cid = session["client_id"]
    period = datetime.now().strftime("%Y-%m")

    try:
        content, manifest = build_archive(request.app.state.db, cid, period)
    except Exception as exc:
        log.error("فشل بناء النسخة الاحتياطية للمنشأة %s: %s", cid, exc, exc_info=True)
        return JSONResponse(
            {"success": False, "error": "تعذّر بناء النسخة الاحتياطية"}, status_code=500
        )

    os.makedirs("backups", exist_ok=True)
    filename = archive_filename(cid, period)
    try:
        with open(os.path.join("backups", filename), "wb") as fh:
            fh.write(content)
    except Exception as exc:
        # القرص مؤقّت على أي حال — الفشل في الحفظ لا يمنع التحميل المباشر
        log.warning("تعذّر حفظ النسخة على القرص: %s", exc)

    return {"success": True, "filename": filename, "manifest": manifest}


@router.get("/api/backup/download")
async def backup_download(request: Request, session=Depends(require_client)):
    """
    يبني النسخة ويُرسلها للتحميل مباشرةً إلى جهاز صاحب المنشأة.

    تُبنى عند الطلب لا تُقرأ من القرص: قرص الحاوية مؤقّت ويُمحى عند كل
    نشر، فالقراءة منه تُعيد «غير موجود» بعد أول إعادة تشغيل.
    """
    from services.backup_archive import archive_filename, build_archive

    _require_backup_access(session)
    cid = session["client_id"]
    period = request.query_params.get("period") or datetime.now().strftime("%Y-%m")

    content, manifest = build_archive(request.app.state.db, cid, period)
    filename = archive_filename(cid, period)
    log.info(
        "تحميل نسخة احتياطية — منشأة=%s شهر=%s صفوف=%s",
        cid, period, manifest["total_rows"],
    )
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Backup-SHA256": manifest["sha256"],
            "X-Backup-Rows": str(manifest["total_rows"]),
        },
    )


@router.get("/api/backup/list")
async def backup_list(request: Request, session=Depends(require_client)):
    """يسرد النسخ المحفوظة على القرص المؤقّت لهذه المنشأة وحدها."""
    _require_backup_access(session)
    cid = session["client_id"]
    prefix = f"duyuf_backup_{cid}_"
    if not os.path.isdir("backups"):
        return {"success": True, "backups": [], "note": "لا نسخ محفوظة بعد"}
    files = sorted(
        (f for f in os.listdir("backups") if f.startswith(prefix)), reverse=True
    )
    return {
        "success": True,
        "backups": files,
        "note": "القرص مؤقّت — نزّل النسخة إلى جهازك للحفظ الدائم",
    }


