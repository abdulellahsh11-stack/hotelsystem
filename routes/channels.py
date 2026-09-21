#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
مسارات مدير القنوات (OTA Channel Manager)
=========================================
ربط، مزامنة، واستقبال حجوزات منصات التوزيع العالمية.
"""
import json
import logging
import threading
from typing import Optional

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/channels", tags=["Channels"])

logger = logging.getLogger("dheuof")


def _require_client(request: Request) -> dict:
    from main import require_client
    return require_client(request)


def _mgr(request: Request):
    mgr = getattr(request.app.state, "channels", None)
    if mgr is None:
        raise HTTPException(status_code=503, detail="خدمة القنوات غير متاحة")
    return mgr


@router.get("/supported")
async def supported(request: Request, session=Depends(_require_client)):
    """قائمة القنوات المدعومة عبر الوسيط."""
    try:
        return {"success": True, "data": _mgr(request).supported_channels()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in supported: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/connections")
async def connections(request: Request, session=Depends(_require_client)):
    """حالة ربط كل قناة لهذا المشترك."""
    try:
        return {"success": True, "data": _mgr(request).list_connections(session["client_id"])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in connections: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/connect")
async def connect(request: Request, session=Depends(_require_client)):
    """ربط قناة بمفتاح API (يُخزَّن مقنّعاً فقط)."""
    try:
        body = await request.json()
        code = (body.get("channel_code") or "").strip()
        api_key = body.get("api_key") or ""
        try:
            result = _mgr(request).connect(session["client_id"], code, api_key)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in connect: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/disconnect")
async def disconnect(request: Request, session=Depends(_require_client)):
    try:
        body = await request.json()
        code = (body.get("channel_code") or "").strip()
        ok = _mgr(request).disconnect(session["client_id"], code)
        return {"success": ok}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in disconnect: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/sync")
async def sync(request: Request, session=Depends(_require_client)):
    """دفع التوافر والأسعار إلى قناة محددة أو لكل القنوات المتصلة."""
    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        code = (body.get("channel_code") or "").strip() or None
        return {"success": True, "data": _mgr(request).sync_rates(session["client_id"], code)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/reservations")
async def reservations(request: Request, status: Optional[str] = None, session=Depends(_require_client)):
    """الحجوزات الواردة من القنوات."""
    try:
        data = _mgr(request).list_reservations(session["client_id"], status)
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reservations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.get("/log")
async def sync_log(request: Request, session=Depends(_require_client)):
    """سجل عمليات المزامنة للتدقيق."""
    try:
        return {"success": True, "data": _mgr(request).sync_log(session["client_id"])}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in sync_log: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


@router.post("/channel-secret/rotate")
async def rotate_channel_secret(request: Request, session=Depends(_require_client)):
    """
    يُنشئ سرّ توقيع جديداً للقنوات ويعرضه **مرة واحدة**.

    لا يُقرأ بعدها: يُخزَّن كما هو ليُقارن به، ونقطةُ قراءةٍ دائمة تعني
    أن أي ثغرة قراءة تكشفه. من فقده يُدوّره من جديد.
    """
    from services.channel_auth import generate_secret

    db = request.app.state.db
    cid = session["client_id"]
    if not getattr(db, "use_postgres", False):
        raise HTTPException(status_code=503, detail="قاعدة البيانات غير متاحة")

    secret = generate_secret()
    db.execute("UPDATE clients SET channel_secret=%s WHERE id=%s", (secret, cid))
    logger.info("دُوِّر سرّ القناة للمنشأة %s", cid)
    return {
        "success": True,
        "secret": secret,
        "note": "احفظه الآن — لن يُعرض مرة أخرى",
        "headers": {
            "X-Channel-Token": cid,
            "X-Channel-Timestamp": "<طابع يونكس بالثواني>",
            "X-Channel-Signature": "hmac_sha256(secret, '<timestamp>.<body>')",
        },
    }


@router.post("/webhook/{channel_code}")
async def webhook(channel_code: str, request: Request):
    """
    نقطة استقبال حجوزات القناة (webhook).

    تُوثَّق بتوقيع HMAC على جسم الطلب. الرأس `X-Channel-Token` صار
    مُعرِّفاً للمنشأة لا اعتماداً — الاعتماد هو التوقيع، لأن رقم
    المنشأة يُرسل بالبريد ويظهر في الواجهة فليس سراً.
    """
    from services.channel_auth import ChannelAuthError, verify_request

    try:
        client_id = request.headers.get("X-Channel-Token", "").strip()
        if not client_id:
            raise HTTPException(status_code=401, detail="رمز القناة مفقود")

        # الجسم الخام قبل أي تحليل: التوقيع محسوب على البايتات كما أُرسلت،
        # وإعادةُ ترميز JSON تُغيّرها فيفشل تحقّقٌ صحيح.
        raw_body = await request.body()

        db = request.app.state.db
        row = db.execute(
            "SELECT channel_secret FROM clients WHERE id=%s", (client_id,), fetch="one"
        ) if getattr(db, "use_postgres", False) else None
        secret = (row or {}).get("channel_secret") or ""

        try:
            verify_request(
                secret,
                request.headers.get("X-Channel-Timestamp", ""),
                request.headers.get("X-Channel-Signature", ""),
                raw_body,
            )
        except ChannelAuthError as exc:
            logger.warning("رُفض webhook للمنشأة %s: %s", client_id, exc)
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        try:
            payload = json.loads(raw_body)
        except Exception:
            raise HTTPException(status_code=400, detail="حمولة غير صالحة")
        try:
            result = _mgr(request).ingest_reservation(client_id, channel_code, payload)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="خطأ في الخادم")


# ──────────────────────────────────────────────────────────────
#  مسارات كانت معرَّفة على app بمسار مطلق قبل التقسيم
#  وأصبحت نسبيةً لبادئة هذا الموجِّه
# ──────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────
#  Channels — inline FastAPI routes
# ──────────────────────────────────────────────────────────────
@router.get("/status/{client_id}")
async def channels_status(client_id: str, request: Request, session=Depends(_require_client)):
    # Finding #2 BOLA fix: ignore path client_id — always use session's client_id
    cid = session["client_id"]
    channels = request.app.state.channels
    if not channels:
        return {"success": True, "data": {}}
    try:
        # `get_status` لم توجد قط في `ChannelManager` — كان المسار يرمي
        # ٥٠٠ في كل نداء. الحالة تُبنى من الاتصالات القائمة نفسها.
        connections = channels.list_connections(cid)
        return {
            "success": True,
            "data": {
                "connections": connections,
                "connected": sum(1 for c in connections if c.get("is_active")),
                "total": len(connections),
            },
        }
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/booking-com/webhook")
async def booking_com_webhook(request: Request):
    channels = request.app.state.channels
    if not channels:
        return {"status": "ok"}
    body = await request.body()
    # استيراد كسول كبقيّة الوحدة: app_core يستورد المسارات فيدور الاستيراد
    from app_core import client_ip as _client_ip

    src_ip = _client_ip(request)

    def _process():
        try:
            ch = channels.get_channel("booking.com")
            if ch:
                ch.process_webhook(body.decode(), src_ip)
        except Exception as e:
            logger.error(f"webhook processing: {e}")

    threading.Thread(target=_process, daemon=True).start()
    return {"status": "ok"}


@router.post("/booking-com/settings")
async def booking_com_settings(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    try:
        creds = json.dumps({
            "hotel_id": data.get("hotel_id", ""),
            "api_key": data.get("api_key", ""),
            "username": data.get("username", ""),
        })
        db.execute(
            """INSERT INTO channel_configs(client_id,channel_name,credentials,is_enabled)
               VALUES(%s,'booking.com',%s,false)
               ON CONFLICT(client_id,channel_name)
               DO UPDATE SET credentials=EXCLUDED.credentials,updated_at=NOW()""",
            (cid, creds)
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.post("/mawasim/settings")
async def mawasim_settings(request: Request, session=Depends(_require_client)):
    data = await request.json()
    db = request.app.state.db
    cid = session["client_id"]
    ical_url = data.get("ical_url", "")
    if not ical_url:
        return JSONResponse({"success": False, "error": "رابط iCal مطلوب"}, status_code=400)
    try:
        creds = json.dumps({"ical_url": ical_url})
        db.execute(
            """INSERT INTO channel_configs(client_id,channel_name,credentials,is_enabled)
               VALUES(%s,'mawasim',%s,true)
               ON CONFLICT(client_id,channel_name)
               DO UPDATE SET credentials=EXCLUDED.credentials,is_enabled=true""",
            (cid, creds)
        )
        return {"success": True}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@router.get("/sync-log/{client_id}")
async def sync_log_by_client(client_id: str, request: Request, session=Depends(_require_client)):
    # Finding #2 BOLA fix: always use session's client_id
    cid = session["client_id"]
    db = request.app.state.db
    try:
        rows = db.execute(
            "SELECT * FROM channel_sync_log WHERE client_id=%s ORDER BY created_at DESC LIMIT 50",
            (cid,), fetch="all"
        )
        return {"success": True, "data": [dict(r) for r in (rows or [])]}
    except Exception as e:
        return {"success": True, "data": [], "warning": str(e)}


@router.get("/revenue-split/{client_id}")
async def revenue_split(client_id: str, request: Request, days: int = 30, session=Depends(_require_client)):
    # Finding #2 BOLA fix: always use session's client_id
    cid = session["client_id"]
    channels = request.app.state.channels
    if not channels:
        return {"success": True, "data": {}}
    try:
        data = channels.get_revenue_split(cid, days)
        return {"success": True, "data": data}
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


# ──────────────────────────────────────────────────────────────
#  Pricing — inline FastAPI routes
# ──────────────────────────────────────────────────────────────
