# قائمة إطلاق ميسر — قبل قلب البوابة إلى الوضع الحيّ

هذا الملف يربط كل بندٍ من بنود الإطلاق العشرين بما نُفّذ في الكود وما يبقى
على المشغّل (مفاتيح، تسجيل ويب هوك، إلخ).

## متغيّرات البيئة المطلوبة

| المتغيّر | الغرض |
|---|---|
| `MOYASAR_SECRET_KEY` | مفتاح ميسر السرّي. `sk_test_…` = ساعات الاختبار، `sk_live_…` = الحيّ |
| `MOYASAR_WEBHOOK_SECRET` | سرّ توقيع الويب هوك (HMAC). **فارغه يرفض كل حدث** |

> لا تضع أيّ مفتاحٍ في الكود — من البيئة فقط، كبقيّة الأسرار.

## تسجيل الويب هوك في لوحة ميسر

وجّه ميسر إلى `POST https://<نطاقك>/api/webhooks/moyasar`، واضبط السرّ نفسه
في `MOYASAR_WEBHOOK_SECRET`. رأس التوقيع المقبول: `x-moyasar-signature`
(أو `x-signature`)، بصيغة hex عارية أو `sha256=…`.

## مصفوفة البنود

| # | البند | الحالة | أين |
|---|---|---|---|
| ١ | التحقق من توقيعات الويب هوك | ✅ | `moyasar.verify_signature` (HMAC-SHA256، مقارنة بزمن ثابت) |
| ٢ | المدفوعات الفاشلة | ✅ | `moyasar.classify` → `failed`، تُسجَّل ولا تفعّل اشتراكاً |
| ٣ | الاستردادات | ✅ | `classify` → `refunded`؛ `apply_business` → `past_due`؛ `gateway.refund_payment` |
| ٤ | الترقيات والهبوطات | ✅ | `subscription.change_plan` + `POST /api/subscription/change-plan` |
| ٥ | مفاتيح الإيديمبوتنسي | ✅ | `dedup_key` فريد + `Idempotency-Key` في نداءات البوابة |
| ٦ | حماية الميزات خادميّاً | ✅ | `subscription.can_use` + `require_module()` |
| ٧ | مزامنة حالة الاشتراك مع القاعدة | ✅ | `apply_business` → `activate` → `save_client` |
| ٨ | الاختبار بساعات اختبار ميسر | ✅ | `gateway.is_test_mode` (مفتاح `sk_test_`) + http محقون في الاختبارات |
| ٩ | بوابة الفوترة | ✅ | `routes/billing.py`: `/portal` · `/invoices` · `/checkout` |
| ١٠ | إيصالات البريد | ✅ (بناء+صفّ) | `receipts.build_receipt`/`queue_receipt`؛ الإرسال الفعلي عبر مُرسِلٍ يقرأ `receipt_intents` |
| ١١ | تسجيل كل حدث دفع | ✅ | جدول `payment_events` + `log_event` |
| ١٢ | البطاقات المنتهية | ✅ | `billing_money.is_expired_card`/`card_failure_reason` |
| ١٣ | جمع الضرائب | ✅ | `billing_money.add_vat`/`extract_vat` (١٥٪) — مطبَّقة في `/checkout` |
| ١٤ | قواعد الفترة التجريبية | ✅ | `subscription.start_trial` (٣٠ يوماً) + تنبيه ٢٤ ساعة |
| ١٥ | منع الرسوم المكرّرة | ✅ | `UNIQUE(dedup_key)` + `ON CONFLICT DO NOTHING` |
| ١٦ | العملات المتعدّدة | ✅ | `billing_money.to_minor/from_minor` + جدول الأسّ |
| ١٧ | تدفّق إلغاء يعمل | ✅ | `subscription.cancel` (يُبقي الوصول حتى نهاية المدّة) + `POST /api/subscription/cancel` |
| ١٨ | إعادة محاولة رسائل الديون | ✅ (منطق) | `dunning.next_attempt`/`should_retry`/`dunning_message` |
| ١٩ | التنبيه عند فشل الويب هوك | ✅ | `moyasar.alert_webhook_failure` (يُسجَّل بحالة `alert`) |
| ٢٠ | اختبار التدفّق كاملاً كعميل | ✅ | `tests/test_billing_flow.py` |

## ما يبقى على المشغّل (خارج الكود)

- **مفاتيح ميسر الحيّة** — تُضاف كمتغيّرات بيئة عند الجاهزية.
- **مُرسِل البريد الفعليّ** — البنيتان ٣ و١٠ و١٨ تبنيان الرسائل وتصفّانها في
  `receipt_intents`؛ يبقى ربط مزوّد بريد (SMTP/مزوّد) يقرأ الصفوف ويُرسل
  ويحدّث الحالة، ويستدعي جدول `dunning` لإعادة المحاولة. هذا أثرٌ جانبيّ
  شبكيّ تُرك خارج النواة المُختبَرة عمداً.
- **اختبار حيّ ببطاقةٍ اختبارية** في ساعات ميسر قبل قلب المفتاح إلى `sk_live_`.

## ملاحظة أمنية

معرّف المنشأة يُؤخذ من `metadata.client_id` الموقَّعة فقط — لا من جذر
الحمولة — فلا يستطيع دافعٌ انتحال منشأةٍ أخرى. أيّ حدثٍ يفشل توقيعه لا
يلمس اشتراكاً ولا يسجّل دفعة.
