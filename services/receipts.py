#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services/receipts.py — إيصالات البريد الإلكتروني (بند: إرسال إيصالات البريد).

عند نجاح الدفع تُبنى رسالة إيصالٍ للضيف تحمل اسم المنشأة والمبلغ والعملة
وسطر الضريبة (إن وُجد) ومعرّف الدفعة/مرجعها وتاريخها — بالعربية أو
الإنجليزية.

`build_receipt` **خالصة**: لا تلمس قاعدةً ولا شبكة، فتُختبَر بالكسر. كل
قيمةٍ تنزل في جسم HTML تُهرَّب بلا استثناء (اسم منشأةٍ فيه `<script>` لا
يُنفَّذ في بريد الضيف) — قاعدةٌ مطلقة أقوى من قاعدةٍ باستثناءات.

الإرسال الفعلي طبقةٌ تالية (services/mailer.py وما فوقه)؛ هنا نبني الرسالة
فقط. و`queue_receipt` تسجّل نيّة الإرسال في القاعدة حين تتوفّر PostgreSQL،
وفي التطوير لا تُخزّن ولا تُوهم بالحفظ.
"""
from __future__ import annotations

import html
import json
import logging

log = logging.getLogger("dheuof.receipts")

# نصوص الإيصال لكل لغة — العربية افتراضاً، والإنجليزية بديلاً.
_L = {
    "ar": {
        "subject": "إيصال دفع — {facility}",
        "title": "إيصال دفع",
        "greeting": "شكراً لك، تمّ استلام دفعتك بنجاح.",
        "facility": "المنشأة",
        "amount": "المبلغ",
        "vat": "منها ضريبة القيمة المضافة",
        "payment_id": "معرّف الدفعة",
        "reference": "المرجع",
        "date": "التاريخ",
        "footer": "هذا إيصالٌ آليّ من منصة ضيوف.",
        "dir": "rtl",
        "lang": "ar",
    },
    "en": {
        "subject": "Payment receipt — {facility}",
        "title": "Payment receipt",
        "greeting": "Thank you, your payment was received successfully.",
        "facility": "Facility",
        "amount": "Amount",
        "vat": "Of which VAT",
        "payment_id": "Payment ID",
        "reference": "Reference",
        "date": "Date",
        "footer": "This is an automated receipt from Dheuof.",
        "dir": "ltr",
        "lang": "en",
    },
}


def _lang(lang) -> dict:
    """يختار حزمة النصوص — غير المعروف يعود إلى العربية."""
    return _L.get(str(lang or "ar").strip().lower(), _L["ar"])


def _money(value, currency) -> str:
    """يُنسّق مبلغاً بخانتين مع رمز العملة — غير الرقمي يعود صفراً."""
    try:
        amt = round(float(value or 0), 2)
    except (TypeError, ValueError):
        amt = 0.0
    cur = str(currency or "SAR").strip().upper() or "SAR"
    return f"{amt:.2f} {cur}"


def _facility_name(client: dict, t: dict) -> str:
    """اسم المنشأة من بيانات العميل، أو اسمٌ افتراضيّ محايد."""
    c = client or {}
    name = (c.get("name") or c.get("facility") or c.get("hotel_name") or "").strip()
    return name or ("منشأتك" if t["lang"] == "ar" else "Your facility")


def build_receipt(payment: dict, client: dict, lang: str = "ar") -> dict:
    """يبني رسالة إيصال دفع: {subject, body_text, body_html}.

    يقرأ من `payment`: amount · currency · vat/vat_amount · id/payment_id ·
    reference · date/created_at. القيم كلها تُهرَّب في جسم HTML.
    """
    t = _lang(lang)
    p = payment or {}

    facility = _facility_name(client, t)
    amount = _money(p.get("amount"), p.get("currency"))
    pay_id = str(p.get("payment_id") or p.get("id") or "").strip()
    reference = str(p.get("reference") or "").strip()
    date = str(p.get("date") or p.get("created_at") or "").strip()

    vat_raw = p.get("vat", p.get("vat_amount"))
    vat = None
    if vat_raw not in (None, "", 0, 0.0):
        vat = _money(vat_raw, p.get("currency"))

    subject = t["subject"].format(facility=facility)

    # ── الجسم النصّي ────────────────────────────────────────────────
    lines = [t["title"], "", t["greeting"], "",
             f"{t['facility']}: {facility}",
             f"{t['amount']}: {amount}"]
    if vat:
        lines.append(f"{t['vat']}: {vat}")
    if pay_id:
        lines.append(f"{t['payment_id']}: {pay_id}")
    if reference:
        lines.append(f"{t['reference']}: {reference}")
    if date:
        lines.append(f"{t['date']}: {date}")
    lines += ["", t["footer"]]
    body_text = "\n".join(lines)

    # ── الجسم HTML (كل قيمةٍ تُهرَّب) ───────────────────────────────
    def esc(v: str) -> str:
        return html.escape(str(v), quote=True)

    rows = [(t["facility"], facility), (t["amount"], amount)]
    if vat:
        rows.append((t["vat"], vat))
    if pay_id:
        rows.append((t["payment_id"], pay_id))
    if reference:
        rows.append((t["reference"], reference))
    if date:
        rows.append((t["date"], date))

    tr = "\n".join(
        f'      <tr><td style="color:#64748b;padding:6px 12px">{esc(k)}</td>'
        f'<td style="color:#0F2640;font-weight:600;padding:6px 12px">{esc(v)}</td></tr>'
        for k, v in rows
    )
    body_html = f"""<!DOCTYPE html>
<html lang="{esc(t['lang'])}" dir="{esc(t['dir'])}">
<head><meta charset="UTF-8"></head>
<body style="font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#f1f5f9;margin:0;padding:20px">
  <div style="background:#fff;max-width:520px;margin:0 auto;border-radius:16px;padding:32px">
    <h2 style="color:#0F2640;margin:0 0 8px">{esc(t['title'])}</h2>
    <p style="color:#475569;margin:0 0 20px">{esc(t['greeting'])}</p>
    <table style="width:100%;border-collapse:collapse;font-size:.95rem">
{tr}
    </table>
    <p style="color:#94a3b8;font-size:.8rem;margin-top:24px">{esc(t['footer'])}</p>
  </div>
</body>
</html>"""

    return {"subject": subject, "body_text": body_text, "body_html": body_html}


# ── لمس القاعدة (معزولٌ، يحرس use_postgres) ─────────────────────────

def _pg(db) -> bool:
    return bool(getattr(db, "use_postgres", False))


def queue_receipt(db, payment: dict, client: dict, lang: str = "ar") -> dict:
    """يسجّل نيّة إرسال إيصالٍ في القاعدة، ويعيد شكل النتيجة.

    في التطوير (بلا PostgreSQL) لا يُخزَّن ولا يُوهم بالحفظ — يعيد
    {"sent": False, "persisted": False}. الإرسال الفعليّ عبر مُرسِلٍ
    يقرأ هذه الصفوف لاحقاً (طبقةٌ تالية).
    """
    msg = build_receipt(payment, client, lang)
    p = payment or {}
    c = client or {}
    client_id = str(c.get("id") or c.get("client_id") or "").strip() or None
    to = str(c.get("email") or "").strip() or None
    pay_id = str(p.get("payment_id") or p.get("id") or "").strip() or None

    if not _pg(db):
        return {"sent": False, "persisted": False, "subject": msg["subject"],
                "to": to}

    row = db.execute(
        """INSERT INTO receipt_intents
             (client_id, payment_id, recipient, lang, subject, body_html, status)
           VALUES (%s, %s, %s, %s, %s, %s, 'queued')
           RETURNING id""",
        (client_id, pay_id, to, _lang(lang)["lang"], msg["subject"],
         json.dumps(msg, ensure_ascii=False)),
        fetch="one")
    return {"sent": False, "persisted": bool(row), "subject": msg["subject"],
            "to": to}
