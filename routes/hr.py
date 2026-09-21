#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M06 — الموارد البشرية HR & Payroll"""
import secrets
import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from db.connection import count_of

router = APIRouter(prefix="/api/m06", tags=["HR"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


@router.get("/employees")
async def list_employees(request: Request, status: Optional[str] = None, page: int = 1, per_page: int = 50, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            limit = min(per_page, 200)
            offset = (page - 1) * limit
            q = "SELECT * FROM employees WHERE client_id = %s"
            params = [cid]
            if status:
                q += " AND status = %s"; params.append(status)  # noqa: E702
            count_q = q.replace("SELECT *", "SELECT COUNT(*)", 1)
            count_result = db.execute(count_q, params, fetch="one")
            total = count_of(count_result)
            q += " ORDER BY full_name_ar LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])], "page": page, "per_page": limit, "total": total}
        return {"success": True, "data": [], "page": page, "per_page": per_page, "total": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_employees: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/employees")
async def create_employee(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if not data.get("full_name_ar"):
            raise HTTPException(400, "full_name_ar مطلوب")
        if db.use_postgres:
            if not data.get("employee_id"):
                data["employee_id"] = f"EMP-{secrets.token_hex(4).upper()}"
            row = db.execute("""
                INSERT INTO employees (client_id,employee_id,full_name_ar,full_name_en,
                    national_id,iqama_number,nationality,position,department,
                    phone,email,hire_date,basic_salary,housing_allow,transport_allow,status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (cid, data.get("employee_id"), data["full_name_ar"],
                  data.get("full_name_en"), data.get("national_id"), data.get("iqama_number"),
                  data.get("nationality", "سعودي"), data.get("position", "موظف"),
                  data.get("department"), data.get("phone"), data.get("email"),
                  data.get("hire_date"), float(data.get("basic_salary", 0)),
                  float(data.get("housing_allow", 0)), float(data.get("transport_allow", 0)),
                  data.get("status", "active")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in create_employee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.put("/employees/{emp_id}")
async def update_employee(emp_id: int, request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("""
                UPDATE employees SET full_name_ar=%s,full_name_en=%s,position=%s,
                department=%s,phone=%s,email=%s,basic_salary=%s,housing_allow=%s,
                transport_allow=%s,status=%s,notes=%s
                WHERE id=%s AND client_id=%s
            """, (data.get("full_name_ar"), data.get("full_name_en"), data.get("position"),
                  data.get("department"), data.get("phone"), data.get("email"),
                  float(data.get("basic_salary", 0)), float(data.get("housing_allow", 0)),
                  float(data.get("transport_allow", 0)), data.get("status", "active"),
                  data.get("notes"), emp_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in update_employee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.delete("/employees/{emp_id}")
async def delete_employee(emp_id: int, request: Request, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            db.execute("UPDATE employees SET status='terminated' WHERE id=%s AND client_id=%s", (emp_id, cid))
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in delete_employee: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/attendance")
async def list_attendance(request: Request, date_from: Optional[str] = None,
                          date_to: Optional[str] = None, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT a.*, e.full_name_ar, e.employee_id
                   FROM attendance a JOIN employees e ON a.employee_id = e.id
                   WHERE a.client_id = %s"""
            params = [cid]
            if date_from:
                q += " AND a.work_date >= %s"; params.append(date_from)  # noqa: E702
            if date_to:
                q += " AND a.work_date <= %s"; params.append(date_to)  # noqa: E702
            q += " ORDER BY a.work_date DESC LIMIT 200"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_attendance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/attendance")
async def record_attendance(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            row = db.execute("""
                INSERT INTO attendance (client_id,employee_id,work_date,check_in_time,
                    check_out_time,hours_worked,overtime_hours,status,notes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (client_id,employee_id,work_date) DO UPDATE SET
                    check_out_time=EXCLUDED.check_out_time,
                    hours_worked=EXCLUDED.hours_worked,
                    status=EXCLUDED.status
                RETURNING *
            """, (cid, data.get("employee_id"), data.get("work_date"),
                  data.get("check_in_time"), data.get("check_out_time"),
                  float(data.get("hours_worked", 0)), float(data.get("overtime_hours", 0)),
                  data.get("status", "present"), data.get("notes")), fetch="one")
            return {"success": True, "data": dict(row)}
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in record_attendance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/payroll")
async def list_payroll(request: Request, year: Optional[int] = None,
                       month: Optional[int] = None, session=Depends(_require_client)):
    try:
        db = request.app.state.db
        cid = session["client_id"]
        if db.use_postgres:
            q = """SELECT p.*, e.full_name_ar, e.employee_id
                   FROM payroll p JOIN employees e ON p.employee_id = e.id
                   WHERE p.client_id = %s"""
            params = [cid]
            if year: q += " AND p.period_year = %s"; params.append(year)  # noqa: E701, E702
            if month: q += " AND p.period_month = %s"; params.append(month)  # noqa: E701, E702
            q += " ORDER BY p.period_year DESC, p.period_month DESC"
            rows = db.execute(q, params, fetch="all")
            return {"success": True, "data": [dict(r) for r in (rows or [])]}
        return {"success": True, "data": []}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_payroll: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/payroll/generate")
async def generate_payroll(request: Request, session=Depends(_require_client)):
    try:
        data = await request.json()
        db = request.app.state.db
        cid = session["client_id"]
        year = int(data.get("year", datetime.now().year))
        month = int(data.get("month", datetime.now().month))
        if db.use_postgres:
            employees = db.execute(
                "SELECT * FROM employees WHERE client_id=%s AND status='active'",
                (cid,), fetch="all")
            generated = []
            for emp in (employees or []):
                emp = dict(emp)
                basic = float(emp.get("basic_salary", 0))
                housing = float(emp.get("housing_allow", 0))
                transport = float(emp.get("transport_allow", 0))
                total = basic + housing + transport
                gosi_emp = basic * 0.1
                gosi_er = basic * 0.12
                net = total - gosi_emp
                row = db.execute("""
                    INSERT INTO payroll (client_id,employee_id,period_month,period_year,
                        basic_salary,allowances,net_salary,gosi_employee,gosi_employer,status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')
                    ON CONFLICT DO NOTHING RETURNING *
                """, (cid, emp["id"], month, year, basic, housing + transport, net,
                      gosi_emp, gosi_er), fetch="one")
                if row:
                    generated.append(dict(row))
            return {"success": True, "generated": len(generated)}
        return {"success": True, "generated": 0}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in generate_payroll: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")
