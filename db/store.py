#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db/store.py — Data Access Layer
يستبدل القراءة/الكتابة المباشرة لـ admin_store.json
يدعم Dual-Write: يكتب على PostgreSQL وJSON معاً حتى التأكد من نجاح الـ migration
"""
import json
import logging
from datetime import datetime, date
from typing import Any, List, Optional

from db.connection import DatabasePool

log = logging.getLogger("dheuof.db.store")

# ── حقول الحساب التي لا تملك أعمدةً في جدول clients ──────────────────
# تُحفَظ داخل settings JSONB تحت المفتاح "_account" وتُرفَع للأعلى عند القراءة.
# يصلح الخلل C1: ضياع pass_hash/plan/status/sub_end في وضع PostgreSQL.
_ACCOUNT_FIELDS = (
    "pass_hash", "pass_salt", "plan", "status",
    "sub_start", "sub_end", "sub_price", "trial_end",
    "subscription_expires", "enabled_modules", "is_owner_account",
    "facility_type", "hotel_name",
)


def public_settings(client: dict) -> dict:
    """
    إعدادات المنشأة صالحةً للعرض — بلا حقول الحساب.

    `settings` تحمل مفتاح `_account` وفيه `pass_hash` و`pass_salt`
    (لأن جدول clients لا يملك أعمدةً لها). إعادة الكتلة كما هي عبر HTTP
    تُخرج تجزئة كلمة المرور وملحها، فتُهاجَم دون اتصال؛ ومع حسابات
    الموظفين يكفي أن يُمنح موظفٌ صلاحية `settings` ليقرأ تجزئة المالك.

    التنقية هنا لا في المسار: كل ما يعرض الإعدادات يمرّ من هذا الباب.
    """
    settings = dict((client or {}).get("settings") or {})
    settings.pop("_account", None)
    return settings


# أسرار الحساب — لا تخرج عبر HTTP لأحد، ولا لمالك المنصة.
# ليست مسألة صلاحية بل مسألة انتشار: التجزئة تُكتب في سجلات الخادم
# ووسطاء الشبكة وذاكرة المتصفح، وكل نسخة منها هدفٌ لهجومٍ دون اتصال.
_SECRET_CLIENT_FIELDS = frozenset({"pass_hash", "pass_salt", "api_key", "channel_secret"})


def public_client(client: dict) -> dict:
    """سجل منشأة صالحٌ للعرض — بلا تجزئة ولا ملح ولا مفاتيح."""
    if not client:
        return {}
    out = {k: v for k, v in client.items() if k not in _SECRET_CLIENT_FIELDS}
    out["settings"] = public_settings(client)
    return out


def _lift_account(row: dict) -> dict:
    """يرفع حقول الحساب المخزّنة في settings._account إلى أعلى السجل."""
    if not row:
        return row
    settings = row.get("settings")
    if isinstance(settings, dict):
        acct = settings.get("_account")
        if isinstance(acct, dict):
            for k, v in acct.items():
                row[k] = v
    return row


def _to_dict(row) -> dict:
    """تحويل RealDictRow إلى dict عادي"""
    if row is None:
        return {}
    return _lift_account(dict(row))


def _rows_to_list(rows) -> list:
    """تحويل قائمة RealDictRow إلى list من dicts"""
    if not rows:
        return []
    return [_lift_account(dict(r)) for r in rows]


class DataStore:
    """
    طبقة الوصول للبيانات — واجهة موحدة بين PostgreSQL وJSON.

    dual_write=True  → يكتب على الاثنين (مرحلة الانتقال الآمنة)
    dual_write=False → PostgreSQL فقط (بعد 48h من تأكيد نجاح PG)
    """

    def __init__(self, db: DatabasePool, dual_write: bool = True):
        self.db = db
        self.dual_write = dual_write
        self._use_pg = db.use_postgres

    # ══════════════════════════════════════════════════════════
    #  CLIENTS — المنشآت
    # ══════════════════════════════════════════════════════════

    def get_client(self, client_id: str) -> Optional[dict]:
        if self._use_pg:
            row = self.db.execute(
                "SELECT * FROM clients WHERE id = %s",
                (client_id,), fetch="one"
            )
            return _to_dict(row) if row else None
        # JSON fallback
        data = self.db.json_read()
        clients = data.get("clients", [])
        return next((c for c in clients if str(c.get("id")) == str(client_id)), None)

    def get_all_clients(self) -> List[dict]:
        if self._use_pg:
            rows = self.db.execute(
                "SELECT * FROM clients ORDER BY created_at DESC",
                fetch="all"
            )
            return _rows_to_list(rows)
        data = self.db.json_read()
        return data.get("clients", [])

    def save_client(self, client: dict) -> dict:
        """إنشاء أو تحديث منشأة"""
        client_id = str(client.get("id", ""))
        if not client_id:
            raise ValueError("client_id مطلوب")

        if self._use_pg:
            existing = self.get_client(client_id)
            # C1 fix: خزّن حقول الحساب (كلمة المرور/الخطة/الاشتراك/الوحدات) داخل
            # settings._account لأن جدول clients لا يملك أعمدةً لها.
            settings = dict(client.get("settings") or {})
            settings.pop("_account", None)
            acct = dict((existing or {}).get("settings", {}).get("_account", {})) if isinstance((existing or {}).get("settings"), dict) else {}
            for k in _ACCOUNT_FIELDS:
                if k in client and client[k] is not None:
                    acct[k] = client[k]
            if acct:
                settings["_account"] = acct
            settings_json = json.dumps(settings, ensure_ascii=False)
            inv_json = json.dumps(client.get("invoice_settings", {}), ensure_ascii=False)

            if existing:
                self.db.execute("""
                    UPDATE clients SET
                        name=%s, type=%s, city=%s, region=%s, phone=%s, email=%s,
                        units_count=%s, settings_locked=%s,
                        settings=%s, invoice_settings=%s
                    WHERE id=%s
                """, (
                    client.get("name", client.get("hotel_name", "")),
                    client.get("type", client.get("facility_type", "")),
                    client.get("city", ""),
                    client.get("region", ""),
                    client.get("phone", ""),
                    client.get("email", ""),
                    int(client.get("units_count", 0)),
                    bool(client.get("settings_locked", False)),
                    settings_json, inv_json,
                    client_id,
                ))
            else:
                self.db.execute("""
                    INSERT INTO clients
                        (id, name, type, city, region, phone, email,
                         units_count, settings_locked,
                         settings, invoice_settings)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    client_id,
                    client.get("name", client.get("hotel_name", "")),
                    client.get("type", client.get("facility_type", "")),
                    client.get("city", ""),
                    client.get("region", ""),
                    client.get("phone", ""),
                    client.get("email", ""),
                    int(client.get("units_count", 0)),
                    bool(client.get("settings_locked", False)),
                    settings_json, inv_json,
                ))

        if not self._use_pg or self.dual_write:
            self._json_upsert_client(client)

        return client

    def delete_client(self, client_id: str) -> bool:
        if self._use_pg:
            count = self.db.execute(
                "DELETE FROM clients WHERE id = %s", (client_id,)
            )
            deleted = (count > 0)
        else:
            deleted = False

        if not self._use_pg or self.dual_write:
            data = self.db.json_read()
            before = len(data.get("clients", []))
            data["clients"] = [c for c in data.get("clients", []) if str(c.get("id")) != str(client_id)]
            if len(data["clients"]) < before:
                self.db.json_write(data)
                deleted = True

        return deleted

    # ══════════════════════════════════════════════════════════
    #  GUESTS — النزلاء
    # ══════════════════════════════════════════════════════════

    # ── التشفير عند حدّ التخزين ────────────────────────────────
    #
    # مكانه هنا لا في المسارات: كل قراءةٍ وكتابةٍ لبيانات النزلاء تمرّ
    # بهذه الطبقة، فمسارٌ جديد يُكتب غداً يرث التشفير بلا أن ينتبه
    # كاتبه. لو وُضع في المسارات لكان أولُ مسارٍ يُنسى ثغرةً صامتة.
    @staticmethod
    def _decrypt_guest_row(row: dict) -> dict:
        from services import guest_crypto

        if not guest_crypto.is_enabled():
            return row
        return guest_crypto.decrypt_guest(row)

    def get_guests(self, client_id: str) -> List[dict]:
        if self._use_pg:
            rows = self.db.execute(
                "SELECT * FROM guests WHERE client_id = %s ORDER BY created_at DESC",
                (client_id,), fetch="all"
            )
            return [self._decrypt_guest_row(g) for g in _rows_to_list(rows)]
        return [self._decrypt_guest_row(g)
                for g in self._json_get_client_data(client_id, "guests")]

    def get_guest(self, client_id: str, guest_id: Any) -> Optional[dict]:
        if self._use_pg:
            # `guests.id` عمود SERIAL. معرّفٌ غير رقمي ليس «غير موجود» بل
            # كان يرمي ValueError فيصير ٥٠٠ — وهذا ما كان يُسقط
            # POST /api/guests بالكامل.
            try:
                numeric = int(guest_id)
            except (TypeError, ValueError):
                return None
            row = self.db.execute(
                "SELECT * FROM guests WHERE client_id = %s AND id = %s",
                (client_id, numeric), fetch="one"
            )
            return self._decrypt_guest_row(_to_dict(row)) if row else None
        guests = self._json_get_client_data(client_id, "guests")
        found = next((g for g in guests if str(g.get("id")) == str(guest_id)), None)
        return self._decrypt_guest_row(found) if found else None

    def find_guest_by_id_number(self, client_id: str, id_number: str) -> Optional[dict]:
        """
        يبحث برقم الهوية عبر الفهرس الأعمى.

        الرقم لا يُرسَل إلى قاعدة البيانات إطلاقاً — تُرسَل بصمتُه. فحتى
        سجلّ الاستعلامات البطيئة لا يحوي أرقام هوية.
        """
        if not id_number:
            return None
        from services import guest_crypto

        if not self._use_pg:
            for g in self.get_guests(client_id):
                if str(g.get("id_number") or "") == str(id_number):
                    return g
            return None

        if guest_crypto.is_enabled():
            row = self.db.execute(
                "SELECT * FROM guests WHERE client_id=%s AND id_number_bidx=%s LIMIT 1",
                (client_id, guest_crypto.blind_index(id_number)), fetch="one")
        else:
            row = self.db.execute(
                "SELECT * FROM guests WHERE client_id=%s AND id_number=%s LIMIT 1",
                (client_id, id_number), fetch="one")
        return self._decrypt_guest_row(_to_dict(row)) if row else None

    def save_guest(self, client_id: str, guest: dict) -> dict:
        from services import guest_crypto

        # `birth_date` كان يُجمَع في نموذج التسجيل ولا يُكتب إطلاقاً —
        # عمودٌ معرَّف في المخطط وغائب عن كلتا الجملتين. أُضيف هنا.
        stored = guest_crypto.encrypt_guest(guest) if guest_crypto.is_enabled() else dict(guest)
        values = (
            stored.get("id_type", ""), stored.get("id_number", ""),
            stored.get("full_name", stored.get("name", "")),
            stored.get("absher_phone", stored.get("phone", "")),
            stored.get("nationality", ""), stored.get("birth_date") or None,
            stored.get("data_status", "incomplete"),
            stored.get("source", ""), stored.get("notes", ""),
            stored.get("id_number_bidx"),
        )

        if self._use_pg:
            guest_id = guest.get("id")
            if guest_id and self.get_guest(client_id, guest_id):
                self.db.execute("""
                    UPDATE guests SET
                        id_type=%s, id_number=%s, full_name=%s,
                        absher_phone=%s, nationality=%s, birth_date=%s,
                        data_status=%s, source=%s, notes=%s, id_number_bidx=%s
                    WHERE client_id=%s AND id=%s
                """, values + (client_id, int(guest_id)))
            else:
                # RETURNING id: المعرّف الحقيقي يُعيده الخادم. بدونه كان
                # المستدعي يتلقّى المعرّف الوهمي الذي اخترعه المسار، فيُنشئ
                # الحجزَ التالي مشيراً إلى نزيلٍ لا وجود له.
                row = self.db.execute("""
                    INSERT INTO guests
                        (client_id, id_type, id_number, full_name,
                         absher_phone, nationality, birth_date, data_status,
                         source, notes, id_number_bidx)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id
                """, (client_id,) + values, fetch="one")
                if row:
                    guest = dict(guest)
                    guest["id"] = _to_dict(row).get("id")

        if not self._use_pg or self.dual_write:
            # مخزن JSON يحفظ المشفَّر أيضاً: ملفٌّ يُنسَخ ويُرسَل بالبريد
            # أسهل تسريباً من قاعدة بيانات.
            self._json_upsert_in_client(client_id, "guests", stored)

        return guest

    def delete_guest(self, client_id: str, guest_id: Any) -> bool:
        if self._use_pg:
            self.db.execute(
                "DELETE FROM guests WHERE client_id=%s AND id=%s",
                (client_id, int(guest_id))
            )
        if not self._use_pg or self.dual_write:
            self._json_remove_from_client(client_id, "guests", guest_id)
        return True

    # ══════════════════════════════════════════════════════════
    #  BOOKINGS — الحجوزات
    # ══════════════════════════════════════════════════════════

    def get_bookings(self, client_id: str, status: Optional[str] = None) -> List[dict]:
        if self._use_pg:
            if status:
                rows = self.db.execute(
                    "SELECT * FROM bookings WHERE client_id=%s AND status=%s ORDER BY check_in DESC",
                    (client_id, status), fetch="all"
                )
            else:
                rows = self.db.execute(
                    "SELECT * FROM bookings WHERE client_id=%s ORDER BY check_in DESC",
                    (client_id,), fetch="all"
                )
            return _rows_to_list(rows)
        bookings = self._json_get_client_data(client_id, "bookings")
        if status:
            bookings = [b for b in bookings if b.get("status") == status]
        return bookings

    def get_booking(self, client_id: str, booking_id: str) -> Optional[dict]:
        if self._use_pg:
            row = self.db.execute(
                "SELECT * FROM bookings WHERE client_id=%s AND id=%s",
                (client_id, booking_id), fetch="one"
            )
            return _to_dict(row) if row else None
        bookings = self._json_get_client_data(client_id, "bookings")
        return next((b for b in bookings if str(b.get("id")) == str(booking_id)), None)

    def save_booking(self, client_id: str, booking: dict) -> dict:
        if self._use_pg:
            bid = str(booking.get("id", ""))
            existing = self.get_booking(client_id, bid) if bid else None
            companions_json = json.dumps(booking.get("companions", []), ensure_ascii=False)
            pre_data_json = json.dumps(booking.get("pre_arrival_data", {}), ensure_ascii=False)

            if existing:
                self.db.execute("""
                    UPDATE bookings SET
                        guest_id=%s, room_id=%s, check_in=%s, check_out=%s,
                        nightly_rate=%s, total_room=%s, status=%s, source=%s,
                        company_name=%s, companions=%s, pre_arrival_status=%s,
                        pre_arrival_data=%s, notes=%s
                    WHERE client_id=%s AND id=%s
                """, (
                    booking.get("guest_id"), booking.get("room_id"),
                    booking.get("check_in"), booking.get("check_out"),
                    booking.get("nightly_rate", 0), booking.get("total_room", 0),
                    booking.get("status", "confirmed"), booking.get("source", "reception"),
                    booking.get("company_name", ""), companions_json,
                    booking.get("pre_arrival_status", "pending"), pre_data_json,
                    booking.get("notes", ""),
                    client_id, bid,
                ))
            else:
                self.db.execute("""
                    INSERT INTO bookings
                        (id, client_id, guest_id, room_id, check_in, check_out,
                         nightly_rate, total_room, status, source, company_name,
                         companions, pre_arrival_token, pre_arrival_status,
                         pre_arrival_data, notes)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    bid, client_id,
                    booking.get("guest_id"), booking.get("room_id"),
                    booking.get("check_in"), booking.get("check_out"),
                    booking.get("nightly_rate", 0), booking.get("total_room", 0),
                    booking.get("status", "confirmed"), booking.get("source", "reception"),
                    booking.get("company_name", ""), companions_json,
                    # NULL لا "" — العمود UNIQUE، وPostgreSQL يعتبر النصّ
                    # الفارغ قيمةً حقيقية بخلاف NULL. فحجزٌ بلا رمزٍ يمرّ،
                    # والثاني يصطدم بقيد التفرّد ويفشل بـ500 — أي أن المنصة
                    # تقبل حجزاً واحداً فقط ثم ترفض كل ما بعده.
                    booking.get("pre_arrival_token") or None,
                    booking.get("pre_arrival_status", "pending"), pre_data_json,
                    booking.get("notes", ""),
                ))

        if not self._use_pg or self.dual_write:
            self._json_upsert_in_client(client_id, "bookings", booking)

        return booking

    # ══════════════════════════════════════════════════════════
    #  POS TRANSACTIONS
    # ══════════════════════════════════════════════════════════

    def get_pos_transactions(self, client_id: str, date_from: Optional[str] = None, date_to: Optional[str] = None) -> List[dict]:
        if self._use_pg:
            if date_from and date_to:
                rows = self.db.execute(
                    "SELECT * FROM pos_transactions WHERE client_id=%s AND date BETWEEN %s AND %s ORDER BY created_at DESC",
                    (client_id, date_from, date_to), fetch="all"
                )
            else:
                rows = self.db.execute(
                    "SELECT * FROM pos_transactions WHERE client_id=%s ORDER BY created_at DESC LIMIT 500",
                    (client_id,), fetch="all"
                )
            return _rows_to_list(rows)
        return self._json_get_client_data(client_id, "pos_transactions")

    def save_pos_transaction(self, client_id: str, tx: dict) -> dict:
        if self._use_pg:
            self.db.execute("""
                INSERT INTO pos_transactions
                    (client_id, booking_id, date, payment_method, amount,
                     vat_amount, net_amount, category, description, cashier)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                client_id, tx.get("booking_id"),
                tx.get("date", str(date.today())),
                tx.get("payment_method", "cash"),
                float(tx.get("amount", 0)),
                float(tx.get("vat_amount", 0)),
                float(tx.get("net_amount", 0)),
                tx.get("category", ""), tx.get("description", ""),
                tx.get("cashier", ""),
            ))

        if not self._use_pg or self.dual_write:
            self._json_append_to_client(client_id, "pos_transactions", tx)

        return tx

    # ══════════════════════════════════════════════════════════
    #  INVOICES — الفواتير
    # ══════════════════════════════════════════════════════════

    def get_invoices(self, client_id: str) -> List[dict]:
        if self._use_pg:
            rows = self.db.execute(
                "SELECT * FROM invoices WHERE client_id=%s ORDER BY created_at DESC",
                (client_id,), fetch="all"
            )
            return _rows_to_list(rows)
        return self._json_get_client_data(client_id, "invoices")

    def save_invoice(self, client_id: str, invoice: dict) -> dict:
        if self._use_pg:
            line_items_json = json.dumps(invoice.get("line_items", []), ensure_ascii=False)
            try:
                self.db.execute("""
                    INSERT INTO invoices
                        (id, client_id, booking_id, guest_id, issue_date,
                         subtotal, vat_amount, total_amount,
                         payment_method, payment_status, line_items)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET
                        payment_status=EXCLUDED.payment_status,
                        whatsapp_sent=EXCLUDED.whatsapp_sent
                """, (
                    invoice.get("id", invoice.get("invoice_number", "")),
                    client_id, invoice.get("booking_id"),
                    invoice.get("guest_id"),
                    invoice.get("issue_date", str(date.today())),
                    float(invoice.get("subtotal", 0)),
                    float(invoice.get("vat_amount", 0)),
                    float(invoice.get("total_amount", 0)),
                    invoice.get("payment_method", "cash"),
                    invoice.get("payment_status", "paid"),
                    line_items_json,
                ))
            except Exception as e:
                log.warning(f"save_invoice PG error: {e}")

        if not self._use_pg or self.dual_write:
            self._json_upsert_in_client(client_id, "invoices", invoice)

        return invoice

    def get_next_invoice_seq(self, client_id: str) -> int:
        """يُعيد رقم الفاتورة التالي ويزيده (atomic)"""
        if self._use_pg:
            row = self.db.execute("""
                INSERT INTO sequences (client_id, invoice_seq)
                VALUES (%s, 1)
                ON CONFLICT (client_id) DO UPDATE
                    SET invoice_seq = sequences.invoice_seq + 1
                RETURNING invoice_seq
            """, (client_id,), fetch="one")
            return row["invoice_seq"] if row else 1
        # JSON fallback — يستخدم عداد في admin_store
        data = self.db.json_read()
        seqs = data.setdefault("invoice_sequences", {})
        seqs[client_id] = seqs.get(client_id, 0) + 1
        self.db.json_write(data)
        return seqs[client_id]

    # ══════════════════════════════════════════════════════════
    #  WHATSAPP LOG
    # ══════════════════════════════════════════════════════════

    def log_whatsapp(self, client_id: str, entry: dict) -> None:
        if self._use_pg:
            try:
                self.db.execute("""
                    INSERT INTO whatsapp_log
                        (client_id, booking_id, guest_phone, message_type, status, error_message)
                    VALUES (%s,%s,%s,%s,%s,%s)
                """, (
                    client_id, entry.get("booking_id"),
                    entry.get("guest_phone", ""),
                    entry.get("message_type", ""), entry.get("status", "sent"),
                    entry.get("error_message", ""),
                ))
            except Exception as e:
                log.warning(f"log_whatsapp PG error: {e}")

    # ══════════════════════════════════════════════════════════
    #  CHATBOT CONVERSATIONS
    # ══════════════════════════════════════════════════════════

    def get_conversation(self, client_id: str, guest_phone: str, limit: int = 20) -> List[dict]:
        if self._use_pg:
            rows = self.db.execute("""
                SELECT role, content, created_at FROM chatbot_conversations
                WHERE client_id=%s AND guest_phone=%s
                ORDER BY created_at DESC LIMIT %s
            """, (client_id, guest_phone, limit), fetch="all")
            return list(reversed(_rows_to_list(rows)))
        # JSON fallback
        data = self.db.json_read()
        convs = data.get("chatbot_conversations", {})
        key = f"{client_id}_{guest_phone}"
        return convs.get(key, [])[-limit:]

    def append_conversation(self, client_id: str, guest_phone: str, role: str, content: str) -> None:
        if self._use_pg:
            try:
                self.db.execute("""
                    INSERT INTO chatbot_conversations (client_id, guest_phone, role, content)
                    VALUES (%s,%s,%s,%s)
                """, (client_id, guest_phone, role, content))
            except Exception as e:
                log.warning(f"append_conversation PG error: {e}")

        if not self._use_pg or self.dual_write:
            data = self.db.json_read()
            convs = data.setdefault("chatbot_conversations", {})
            key = f"{client_id}_{guest_phone}"
            convs.setdefault(key, []).append({
                "role": role, "content": content,
                "created_at": datetime.now().isoformat(),
            })
            # الاحتفاظ بآخر 50 رسالة فقط في JSON
            convs[key] = convs[key][-50:]
            self.db.json_write(data)

    # ══════════════════════════════════════════════════════════
    #  ADMIN STORE — للمالك (العملاء + الاشتراكات + التذاكر)
    # ══════════════════════════════════════════════════════════

    def get_admin_data(self) -> dict:
        """يُعيد كامل admin_store لأغراض التوافق مع main_admin.py"""
        return self.db.json_read()

    def save_admin_data(self, data: dict) -> bool:
        """يحفظ admin_store — للتوافق مع main_admin.py"""
        return self.db.json_write(data)

    # ══════════════════════════════════════════════════════════
    #  JSON Helpers — داخلية فقط
    # ══════════════════════════════════════════════════════════

    def _json_get_client_data(self, client_id: str, key: str) -> list:
        data = self.db.json_read()
        clients = data.get("clients", [])
        client = next((c for c in clients if str(c.get("id")) == str(client_id)), None)
        if client:
            return client.get(key, [])
        # منشأة غير موجودة تحصل على لا شيء.
        # كان هنا سقوطٌ إلى `data.get(key)` — أي المفتاح العام المشترك —
        # فتُعاد بياناتُ منشآت أخرى لمن لا سجلّ له. تسريبٌ عبر المستأجرين
        # يظهر عند أول منشأة جديدة أو كتابة ناقصة.
        return []

    def _json_upsert_client(self, client: dict) -> None:
        client_id = str(client.get("id", ""))
        data = self.db.json_read()
        clients = data.setdefault("clients", [])
        idx = next((i for i, c in enumerate(clients) if str(c.get("id")) == client_id), None)
        if idx is not None:
            clients[idx] = client
        else:
            clients.append(client)
        self.db.json_write(data)

    def _json_upsert_in_client(self, client_id: str, key: str, item: dict) -> None:
        item_id = str(item.get("id", ""))
        data = self.db.json_read()
        clients = data.get("clients", [])
        client = next((c for c in clients if str(c.get("id")) == str(client_id)), None)
        if client is not None:
            items = client.setdefault(key, [])
            if item_id:
                idx = next((i for i, x in enumerate(items) if str(x.get("id")) == item_id), None)
                if idx is not None:
                    items[idx] = item
                    self.db.json_write(data)
                    return
            items.append(item)
            self.db.json_write(data)

    def _json_append_to_client(self, client_id: str, key: str, item: dict) -> None:
        data = self.db.json_read()
        clients = data.get("clients", [])
        client = next((c for c in clients if str(c.get("id")) == str(client_id)), None)
        if client is not None:
            client.setdefault(key, []).append(item)
            self.db.json_write(data)

    def _json_remove_from_client(self, client_id: str, key: str, item_id: Any) -> None:
        data = self.db.json_read()
        clients = data.get("clients", [])
        client = next((c for c in clients if str(c.get("id")) == str(client_id)), None)
        if client is not None:
            client[key] = [x for x in client.get(key, []) if str(x.get("id")) != str(item_id)]
            self.db.json_write(data)
