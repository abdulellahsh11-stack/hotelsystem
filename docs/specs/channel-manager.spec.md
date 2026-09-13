# مواصفة: مدير القنوات (Channel Manager) — متعدّد المنصّات، ثنائيّ الاتجاه

**الحالة:** Draft · **الأولوية:** P1 (بعد الامتثال P0) · **النموذج:** Per-Tenant Provider Adapters

---

## ١. WHAT / WHY

منصّات الحجز **متعدّدة** ولا تقتصر على Booking.com: **المسافر (Almosafer) ·
اقودا (Agoda) · Expedia · Airbnb** وغيرها. يجب أن يزامن ضيوف معها جميعاً
**في الاتجاهين**، مع **تخصيصٍ لكل مشترك** (أيّ قنوات يربط، وكيف يُطابق غرفه).

### التدفّقان
- **وارد (OTA → ضيوف):** الحجوزات الجديدة/التعديلات/الإلغاءات تُنقَل إلى ضيوف.
- **صادر (ضيوف → OTA):** **التوفّر والأسعار والقيود** تُدفَع من ضيوف إلى كل قناة مربوطة.

### مصدر الحقيقة
**التوفّر والأسعار في ضيوف هما مصدر الحقيقة** (كما في مواصفة المعمارية).
القنوات تعكس ما يقوله ضيوف، لا العكس — فمنع الحجز المزدوج (Overbooking) ممكن.

---

## ٢. لكل مشترك قنواته واعتماداته

كل منشأةٍ تربط قنواتها بنفسها وتُدخل **اعتمادها الخاص** لكل قناة (كنموذج
الزكاة/شموس). ضيوف محايدٌ تجاه القناة (Channel-agnostic).

```
channel_accounts(client_id, channel, credentials_enc, property_ext_id,
                 enabled, env, created_at,
                 PRIMARY KEY(client_id, channel))   -- channel: booking|almosafer|agoda|expedia...
channel_room_map(client_id, channel, dheuof_room_type_id, channel_room_id,
                 dheuof_rate_plan_id, channel_rate_id,
                 PRIMARY KEY(client_id, channel, dheuof_room_type_id))
channel_reservations(id, client_id, channel, channel_res_id UNIQUE,
                     dheuof_booking_id, status, payload_raw, created_at)
channel_sync_log(id, client_id, channel, direction, entity, status,
                 request_raw, response_raw, created_at)
```

> **إصلاحٌ لعطبٍ قائم:** يُوحَّد هذا الجدول محلّ ازدواج `channel_configs` /
> `channel_connections`. الاعتماد يُخزَّن **مشفّراً** (لا قناعاً غير قابل
> للاستخدام)، ويُعرَض **مقنّعاً** للمشترك، ولا يُقرأ من بيئةٍ مركزية.

---

## ٣. التصميم (محوّل لكل قناة)

```
ضيوف Core (Availability · Rate · Reservation — مصدر الحقيقة)
        │   صادر: توفّر/سعر/قيود        ▲ وارد: حجز/تعديل/إلغاء
        ▼                               │
Channel Manager (تنسيق · طابور · مطابقة · reconciliation)
        │
        ├─ BookingAdapter   (Connectivity XML/JSON)   ⚠ توثيق رسمي
        ├─ AlmosaferAdapter                            ⚠ توثيق رسمي
        ├─ AgodaAdapter (YCS)                          ⚠ توثيق رسمي
        └─ ExpediaAdapter (EQC)                        ⚠ توثيق رسمي
```
واجهة موحّدة:
```
class Channel(Protocol):
    def push_availability(room_map, dates, avail, rates, restrictions) -> result
    def pull_reservations(since) -> [reservation]
    def ack_reservation(channel_res_id) -> None
```
> **لا API مُخترَع:** كل محوّلٍ يُبنى على **التوثيق الرسمي للقناة** فقط؛ غير الموثّق يبقى `TODO`.

---

## ٤. ربط الكيانات (Mapping) والتخصيص

| ضيوف | ↔ | القناة |
|---|---|---|
| Property | ↔ | Property/Hotel ID |
| Room Type | ↔ | Channel Room |
| Rate Plan | ↔ | Channel Rate |
| Reservation | ↔ | Channel Reservation |

المشترك يخصّص: أيّ أنواع غرفٍ تُعرَض على أيّ قناة، وأيّ خطة سعر، وحدود التوفّر
(مثلاً حجب نسبة للبيع المباشر). `channel_room_map` يحمل هذا التخصيص لكل منشأة.

---

## ٥. الصحّة والموثوقية (لا مجال للحجز المزدوج)

| المتطلّب | الآلية |
|---|---|
| منع الحجز المزدوج | ضيوف مصدر التوفّر؛ دفعٌ فوريّ للتوفّر عند كل حجز/إلغاء |
| Idempotency | `channel_res_id` فريد وارداً؛ مفتاح دفعٍ صادراً — لا تكرار |
| Retry/Backoff | فشل القناة → طابور + إعادة أسّية (نمط dunning) |
| Reconciliation | مهمة دورية تُطابق توفّر ضيوف بما لدى القناة وتُصحّح الانحراف |
| Webhook/Polling | وارد عبر webhook حيث تدعمه القناة، وإلا polling دوري |
| Audit | كل تبادلٍ (اتجاه/كيان/طلب/استجابة) في `channel_sync_log` |
| العزل | كل صفٍّ بـ`client_id` |

---

## ٦. حدود الأخطاء
- قناةٌ بلا اعتمادٍ مربوط → «غير مربوطة»، لا مزامنة صامتة.
- تعارض توفّر (Overbooking محتمل) → ضيوف يفوز، ويُسجَّل الانحراف وينبَّه.
- حجزٌ وارد بغرفةٍ غير مُطابَقة (`channel_room_map`) → يُوقَف ويُعرَض للمطابقة اليدوية، لا يُسقَط.
- تكرار حجز → يُكشف بـ`channel_res_id`.

## ٧. خطة الاختبار
1. **وحدة:** المطابقة · بناء حمولة التوفّر/السعر · `dedup` (بلا شبكة).
2. **عقد المحوّل:** Fake Channel لكل قناة يطابق الواجهة الموحّدة.
3. **كسر:** حجز مكرّر → صفٌّ واحد · حجز بغرفة غير مُطابَقة → يُوقَف · إلغاء يحرّر التوفّر.
4. **Reconciliation:** انحراف توفّر مُفتعَل → تُصحّحه المهمة.
5. **Sandbox:** دورة كاملة لكل قناة في بيئتها التجريبية قبل الإنتاج.

**معيار القبول:** مزامنةٌ ثنائية لكل قناةٍ مربوطة عبر محوّلٍ محايد، بمصدر
حقيقةٍ واحد (ضيوف) ومنع حجزٍ مزدوج، واعتمادٌ لكل مشترك مشفّرٌ ومقنّع.
