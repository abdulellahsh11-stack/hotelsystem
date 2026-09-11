# الخطة والمهام — تكاملا ZATCA وشموس

## الخطة التقنية (Plan)

### طبقات مشتركة (تُبنى أولاً — تخدم التكاملين)
1. **Government Integration Layer** (`services/gov/`): تنسيق، طابور، إعادة محاولة أسّية، تدقيق خام، عزل بالمنشأة.
2. **Credential Vault**: تخزين مفاتيح/CSID/توكنات مشفّرةً بمفتاح منفصل (`ZATCA_KEY_ENCRYPTION`)، على نمط `services/guest_encryption`.
3. **Audit + Reconciliation**: جداول خام + مهمة دورية (APScheduler موجود) تُطابق وتُبرز المتخلّف.

### ترتيب التنفيذ
```
Phase A: الطبقات المشتركة + نماذج البيانات + الاختبارات (بلا شبكة)
Phase B: ZATCA — Onboarding → Simplified(Reporting) → Standard(Clearance) في Sandbox
Phase C: شموس — كل المنطق الداخلي خلف واجهة Adapter + Fake (بانتظار المواصفة الرسمية)
Phase D: Reconciliation + لوحات حالة الامتثال في BI
Phase E: تفعيل الإنتاج بعد الاعتمادات الرسمية
```

## المهام (Tasks)

### ZATCA (P0) — **مُرحَّل لمزوّد معتمَد، لكل مشترك مزوّده**
ضيوف = محاسبة عامّة + محوّل محايد. التوقيع/التخليص عند المزوّد (ترحيل المسؤولية).
- [ ] `db/migrations`: `zatca_provider_config` (لكل `client_id`: مزوّد + API + اعتمادات مشفّرة) و`zatca_submissions` (dedup فريد + تدقيق).
- [ ] `services/gov/zatca/provider.py`: واجهة `ZatcaProvider` موحّدة (`submit_invoice`/`submit_credit_note`/`status`).
- [ ] `services/gov/zatca/adapters/`: محوّل لكل مزوّد (ClearTax · InvoiceQ · Wafeq …) — يُضاف عند الطلب.
- [ ] `services/gov/zatca/payload.py`: بناء حمولة الفاتورة العامّة من المحاسبة.
- [ ] `services/gov/zatca/submit.py`: إرسال عند الطلب + Idempotency + Retry + تخزين الاستجابة الخام.
- [ ] `services/gov/zatca/reconcile.py`: مهمة دورية تُبرز غير المُخلّص/المرفوض.
- [ ] `routes/zatca.py`: ربط المشترك بمزوّده · إرسال/إعادة/حالة (بحارس `require_manager`).
- [ ] اختبارات: عقد المحوّل بـFake Provider · إرسال بلا مزوّد (لا ادّعاء امتثال) · إيديمبوتنسي · رفض المزوّد · Sandbox.
- [ ] **تحقّق تشغيلي**: تثبيت قائمة المزوّدين المعتمَدين من موقع ZATCA + DPA لكل مزوّد.

### شموس (P0 — محجوبٌ باعتمادٍ رسمي)
- [ ] `db/migrations`: جدول `shomoos_registrations` (dedup فريد).
- [ ] `services/gov/shomoos/model.py`: حزمة النزيل الداخلية + تقليل البيانات.
- [ ] `services/gov/shomoos/adapter.py`: **واجهة** `register/update` — `NotImplemented` حتى المواصفة الرسمية.
- [ ] `services/gov/shomoos/queue.py`: طابور + إعادة محاولة + تدقيق.
- [ ] `services/gov/shomoos/reconcile.py`: إبراز الحجوزات غير المُسجَّلة.
- [ ] ربط حدث check-in في `routes/hotel_ops.py`.
- [ ] اختبارات: عقد المحوّل بـFake · كسر (نزيل بلا هوية) · إيديمبوتنسي · reconciliation.

## الاعتماديات
| المهمة | تعتمد على |
|---|---|
| ZATCA client | onboarding + invoice builder |
| شموس adapter الحقيقي | **المواصفة/الاتفاقية الرسمية + اعتماد ضيوف** |
| تفعيل الإنتاج | اجتياز Sandbox + الاعتمادات الرسمية |

## معايير القبول (Definition of Done)
1. لا تُطبع فاتورة «صالحة» إلا بحالة `CLEARED`/`REPORTED`.
2. لا يُتمّ check-in بتسجيل شموس صامتٍ ناقص.
3. كل مسارٍ مغطّى باختبار كسرٍ قبل الوثوق به.
4. كل إرسال/استجابة في سجلّ تدقيق قابلٍ للمطابقة.
5. الأسرار مشفّرة ولا تخرج عبر HTTP.
6. Sandbox أخضر قبل أي إنتاج.

## المخاطر
- **غياب مواصفة شموس** → بناء كل الداخلي خلف واجهة، وعدم تفعيلٍ إنتاجي قبل الاعتماد (لا كود سلك مُخترَع).
- **تعقيد التوقيع ZATCA** → الاعتماد على متّجهات الاختبار الرسمية والتحقق بالكسر.
- **الوقت (موجة يونيو ٢٠٢٦)** → ZATCA أولاً بالتوازي مع مسار الاعتماد.
