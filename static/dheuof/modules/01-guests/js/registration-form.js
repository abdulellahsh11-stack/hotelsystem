// registration-form.js — منطق النموذج الأصلي (الحقول والحساب والعرض)
//
// مُستخرَج من registration.html. الحفظ والغرف والأقسام الاختيارية
// في registration-app.js المُحمَّل بعده.

StaticSidebar.mount({ activeId: "01-guests", placeholder: "بحث في النزلاء والحجوزات..." });

// Ensure content is always visible — fallback if IntersectionObserver threshold not met
setTimeout(function(){
  document.querySelectorAll('[data-m-rise],[data-m-rise-stagger]').forEach(function(el){
    el.classList.add('is-in');
  });
}, 80);

/* =========================================================================
   Guest Registration — Interactive Logic
   13 functional areas: ID tabs, name priority, nationality, dates,
   time policy, vehicle/driver, SMS trip, payment, pay-link, contract,
   signature, ID scanner.
   ========================================================================= */
(function(){
  function q(s){ return document.querySelector(s); }
  function qq(s){ return Array.prototype.slice.call(document.querySelectorAll(s)); }

  /* ── TOAST ─────────────────────────────────────────────────────── */
  function toast(msg, isErr) {
    var old = q('.dh-toast'); if(old) old.remove();
    var t = document.createElement('div'); t.className = 'dh-toast';
    t.style.cssText = 'position:fixed;bottom:28px;left:50%;transform:translateX(-50%);background:'+(isErr?'var(--danger-700)':'var(--brand-800)')+';color:var(--paper);padding:12px 24px;border-radius:10px;font-family:var(--font-ar);font-size:13.5px;font-weight:500;box-shadow:0 8px 32px rgba(0,0,0,0.28);z-index:9999;white-space:nowrap;display:flex;align-items:center;gap:10px;direction:rtl';
    t.innerHTML = '<span style="color:var(--gold-400)">'+(isErr?'✕':'✓')+'</span> '+msg;
    document.body.appendChild(t);
    setTimeout(function(){ t.style.opacity='0'; t.style.transition='opacity 0.4s'; setTimeout(function(){ if(t.parentNode)t.remove(); },400); }, 3200);
  }
  window.GR = window.GR || {}; window.GR.toast = toast;

  /* ── MODAL ─────────────────────────────────────────────────────── */
  function modal(title, html, wide) {
    var old = q('.dh-modal-bd'); if(old) old.remove();
    var bd = document.createElement('div'); bd.className='dh-modal-bd';
    bd.style.cssText='position:fixed;inset:0;background:rgba(14,42,34,0.65);backdrop-filter:blur(4px);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px';
    bd.addEventListener('click',function(e){ if(e.target===bd)bd.remove(); });
    var w = wide?'min(820px,96vw)':'min(600px,95vw)';
    bd.innerHTML='<div dir="rtl" style="background:var(--white);border-radius:16px;width:'+w+';max-height:88vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 24px 64px -16px rgba(14,42,34,0.45)">'
      +'<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 22px;border-bottom:1px solid var(--hairline);background:var(--paper-tint)">'
        +'<div style="font-family:var(--font-ar-display);font-weight:700;font-size:16px;color:var(--ink-900)">'+title+'</div>'
        +'<button onclick="document.querySelector(\'.dh-modal-bd\').remove()" style="background:transparent;border:1px solid var(--ink-100);color:var(--fg-3);border-radius:6px;padding:5px 14px;cursor:pointer;font-family:var(--font-ar);font-size:12px">✕ إغلاق</button>'
      +'</div>'
      +'<div style="padding:22px;overflow-y:auto;direction:rtl">'+html+'</div>'
    +'</div>';
    document.body.appendChild(bd);
  }

  /* ─── 1. ID TYPE TABS ─────────────────────────────────────────── */
  var ID_CFG = [
    { f1:{lbl:'رقم الهوية الوطنية',req:true,hint:'١٠ أرقام · يبدأ بـ ١',maxlen:10,pl:'1xxxxxxxxx'},
      f2:{lbl:'رقم النسخة',req:true,hint:'ظهر البطاقة',maxlen:2,pl:'XX'},
      f3:{lbl:'تاريخ انتهاء الهوية',req:false,hint:'YYYY-MM-DD',pl:'2030-01-01'} },
    { f1:{lbl:'رقم الهوية الخليجية',req:true,hint:'٦–١٠ أرقام',maxlen:12,pl:'xxxxxxxxxx'},
      f2:{lbl:'الدولة المُصدِرة',req:true,isSelect:true,opts:['الإمارات','الكويت','قطر','البحرين','عُمان']},
      f3:{lbl:'تاريخ انتهاء الهوية',req:true,hint:'YYYY-MM-DD',pl:'2028-01-01'} },
    { f1:{lbl:'رقم الإقامة',req:true,hint:'١٠ أرقام · يبدأ بـ ٢',maxlen:10,pl:'2xxxxxxxxx'},
      f2:{lbl:'تاريخ انتهاء الإقامة',req:true,hint:'YYYY-MM-DD',pl:'2026-06-30'},
      f3:{lbl:'المهنة حسب الإقامة',req:false,hint:'اختياري',pl:'مهندس / معلم...'} },
    { f1:{lbl:'رقم جواز السفر',req:true,hint:'MRZ Code',maxlen:9,pl:'A12345678'},
      f2:{lbl:'الدولة المُصدِرة',req:true,isSelect:true,opts:['السعودية','الإمارات','مصر','الأردن','تركيا','باكستان','الهند','الفلبين','أخرى']},
      f3:{lbl:'تاريخ انتهاء الجواز',req:true,hint:'YYYY-MM-DD',pl:'2028-06-01'} }
  ];

  function setIdField(cell, cfg) {
    var lbl = cell.querySelector('label');
    lbl.innerHTML = cfg.lbl + (cfg.req ? ' <span class="req">*</span>' : '');
    var hint = cell.querySelector('.hint'); if(hint) hint.textContent = cfg.hint||'';
    var old = cell.querySelector('input,select');
    if(cfg.isSelect){
      var sel = document.createElement('select');
      cfg.opts.forEach(function(o){ var op=document.createElement('option'); op.textContent=o; sel.appendChild(op); });
      if(old) old.replaceWith(sel); else cell.appendChild(sel);
    } else {
      var inp = document.createElement('input'); inp.type='text'; inp.className='is-mono';
      if(cfg.maxlen) inp.maxLength=cfg.maxlen; inp.placeholder=cfg.pl||''; inp.value='';
      if(old) old.replaceWith(inp); else cell.appendChild(inp);
    }
  }

  function initIdTabs(){
    var tabs = qq('.gr-id-tab'), grid = q('#gr-id-fields'); if(!grid) return;
    var cells = grid.querySelectorAll('.gr-field');
    tabs.forEach(function(tab,i){
      tab.addEventListener('click', function(){
        tabs.forEach(function(t){ t.classList.remove('is-on'); });
        tab.classList.add('is-on');
        var cfg = ID_CFG[i];
        setIdField(cells[0], cfg.f1); setIdField(cells[1], cfg.f2); setIdField(cells[2], cfg.f3);
      });
    });
  }

  /* ─── 2. NAME LANGUAGE PRIORITY ──────────────────────────────── */
  function initNamePriority(){
    var ar = q('[data-name="ar"]'), en = q('[data-name="en"]'); if(!ar||!en) return;
    var arLbl = ar.closest('.gr-field').querySelector('label');
    var enLbl = document.getElementById('lbl-name-en') || en.closest('.gr-field').querySelector('label');
    function upd(){
      if(en.value.trim() && !ar.value.trim()){
        arLbl.innerHTML='الاسم الكامل (عربي) <span style="font-size:10px;color:var(--fg-3)">(اختياري)</span>';
        enLbl.innerHTML='Full name (Latin) <span class="req">*</span>';
      } else {
        arLbl.innerHTML='الاسم الكامل (عربي) <span class="req">*</span>';
        enLbl.innerHTML='Full name (Latin) <span style="font-size:10px;color:var(--fg-3)">(اختياري)</span>';
      }
    }
    ar.addEventListener('input',upd); en.addEventListener('input',upd); upd();
  }

  /* ─── 4. DATE AUTO-CALCULATION ───────────────────────────────── */
  function initDates(){
    var ci=q('[data-field="checkin"]'), co=q('[data-field="checkout"]'), n=q('[data-field="nights"]');
    if(!ci||!co||!n) return;
    function calcCO(){
      var d=new Date(ci.value), nights=parseInt(n.value);
      if(!isNaN(d.getTime())&&nights>0){ d.setDate(d.getDate()+nights); co.value=d.toISOString().split('T')[0]; co.style.borderColor=''; }
    }
    function calcN(){
      var d1=new Date(ci.value), d2=new Date(co.value);
      if(!isNaN(d1.getTime())&&!isNaN(d2.getTime())){
        var diff=Math.round((d2-d1)/86400000);
        n.value=diff>0?diff:''; co.style.borderColor=diff<=0?'var(--danger-500)':'';
      }
    }
    ci.addEventListener('change',function(){ if(n.value) calcCO(); else if(co.value) calcN(); });
    n.addEventListener('input', calcCO);
    co.addEventListener('change', calcN);

    // افتراضٌ حيّ: الوصول يبدأ بتاريخ اليوم، والمغادرة تُحسب من الليالي —
    // بدل تاريخٍ ثابت قديم (كان ٢٠٢٥). ولا حدّ أدنى (`min`) على أيّهما:
    // الحقلان قابلان للتعديل بحرّية لأي يوم، حتى يومٍ سابق — فمن وصل
    // بعد منتصف الليل (١٢:٠٥ص) وخرج ٣م يُسجَّل وصولُه أمسِ فتُحسب ليلةً.
    if(!ci.value){ ci.value = new Date().toISOString().split('T')[0]; }
    if(!co.value){ if(n.value) calcCO(); else calcN(); }
  }

  /* ─── 5. CHECK-IN/OUT TIME POLICY ────────────────────────────── */
  // السياسة تُقرأ من الخادم وتُحفَظ فيه — لا قيمةٌ ثابتة في الواجهة، ولا
  // زرُّ حفظٍ يدّعي النجاح بلا نداء. الحفظ لمالك المنشأة ومديرها وحدهما
  // (الخادم يفرضه)، وزرّ التعديل يُخفى عمّن لا يملكه بحسب `can_edit`.
  var POLICY = null;          // آخر سياسةٍ حُمِّلت من الخادم
  var POLICY_CAN_EDIT = false;

  // «14:00» → «٢:٠٠م» للعرض العربي.
  function fmtTime(hhmm){
    var m = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm||''));
    if(!m) return hhmm||'';
    var h = parseInt(m[1],10), mer = h<12?'ص':'م', h12 = (h%12)||12;
    var ar = function(s){ return String(s).replace(/\d/g,function(d){ return '٠١٢٣٤٥٦٧٨٩'[+d]; }); };
    return ar(h12)+':'+ar(m[2])+mer;
  }

  function renderPolicyHint(){
    var hint = q('#arr-time-hint'); if(!hint || !POLICY) return;
    var edit = POLICY_CAN_EDIT
      ? ' · <span id="edit-policy" style="color:var(--gold-700);cursor:pointer;text-decoration:underline;font-size:10px">تعديل السياسة</span>'
      : '';
    hint.innerHTML='سياسة الفندق: الدخول <strong style="color:var(--brand-700)">'+fmtTime(POLICY.checkin_time)+'</strong>'
      +' · الخروج <strong style="color:var(--brand-700)">'+fmtTime(POLICY.checkout_time)+'</strong>'+edit;
    var ep = document.getElementById('edit-policy');
    if(ep) ep.addEventListener('click', openPolicyModal);
  }

  function openPolicyModal(){
    var p = POLICY || {};
    modal('سياسة الدخول والخروج — تخصيص المنشأة',
      '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">'
        +'<div class="gr-field"><label style="font-size:12px;font-weight:500">وقت الدخول الافتراضي</label>'
          +'<input id="pol-ci" type="time" value="'+(p.checkin_time||'14:00')+'" style="font-family:var(--font-mono);padding:10px;border:1px solid var(--ink-100);border-radius:6px;font-size:14px;width:100%"/>'
          +'<span style="font-size:11px;color:var(--fg-3)">Check-in · سياسة الفندق</span></div>'
        +'<div class="gr-field"><label style="font-size:12px;font-weight:500">وقت الخروج الافتراضي</label>'
          +'<input id="pol-co" type="time" value="'+(p.checkout_time||'12:00')+'" style="font-family:var(--font-mono);padding:10px;border:1px solid var(--ink-100);border-radius:6px;font-size:14px;width:100%"/>'
          +'<span style="font-size:11px;color:var(--fg-3)">Check-out · سياسة الفندق</span></div>'
      +'</div>'
      +'<div style="background:var(--gold-50);border:1px solid var(--gold-200);border-radius:10px;padding:14px;font-size:12px;margin-bottom:14px">'
        +'<div style="font-weight:600;margin-bottom:8px">الحالات الخاصة</div>'
        +'<label style="display:flex;align-items:center;gap:8px;cursor:pointer;margin-bottom:8px"><input id="pol-early" type="checkbox" '+(p.early_checkin_free?'checked':'')+' style="accent-color:var(--brand-700)"/> السماح بالدخول المبكر عند توفر الغرفة (بدون رسوم)</label>'
        +'<label style="display:flex;align-items:center;gap:8px;cursor:pointer"><input id="pol-late" type="checkbox" '+(p.late_checkout_fee_enabled?'checked':'')+' style="accent-color:var(--brand-700)"/> تأخير الخروج بمقابل إضافي — <input id="pol-fee" type="number" min="0" value="'+(p.late_checkout_fee!=null?p.late_checkout_fee:200)+'" style="width:80px;padding:4px 8px;border:1px solid var(--ink-100);border-radius:4px;font-size:12px"/> ر.س لكل <input id="pol-block" type="number" min="1" value="'+(p.late_checkout_block_hours||3)+'" style="width:56px;padding:4px 8px;border:1px solid var(--ink-100);border-radius:4px;font-size:12px"/> ساعات</label>'
      +'</div>'
      +'<button id="pol-save" style="font-family:var(--font-ar);font-size:13px;font-weight:600;padding:10px;border-radius:8px;background:var(--brand-700);color:var(--paper);border:none;cursor:pointer;width:100%">حفظ السياسة</button>'
    );
    var btn = document.getElementById('pol-save');
    if(btn) btn.addEventListener('click', savePolicy);
  }

  // حفظٌ حقيقي: يُرسل السياسة للخادم، ولا يُعلن النجاح إلا على ردٍّ ناجح.
  function savePolicy(){
    var btn = document.getElementById('pol-save');
    var body = {
      checkin_time: (q('#pol-ci')||{}).value || '14:00',
      checkout_time: (q('#pol-co')||{}).value || '12:00',
      early_checkin_free: !!(q('#pol-early')||{}).checked,
      late_checkout_fee_enabled: !!(q('#pol-late')||{}).checked,
      late_checkout_fee: parseInt((q('#pol-fee')||{}).value,10) || 0,
      late_checkout_block_hours: parseInt((q('#pol-block')||{}).value,10) || 3
    };
    if(btn){ btn.disabled=true; btn.textContent='جارٍ الحفظ…'; }
    fetch('/api/settings/stay-policy', {
      method:'POST', credentials:'same-origin',
      headers:{ 'Content-Type':'application/json', 'Accept':'application/json' },
      body: JSON.stringify(body)
    }).then(function(res){
      return res.json().catch(function(){ return {}; }).then(function(b){ return {ok:res.ok, b:b}; });
    }).then(function(r){
      if(!r.ok){
        if(btn){ btn.disabled=false; btn.textContent='حفظ السياسة'; }
        toast((r.b && (r.b.detail||r.b.error)) || 'تعذّر حفظ السياسة', true);
        return;
      }
      POLICY = (r.b && r.b.data && r.b.data.policy) || body;
      var bd=q('.dh-modal-bd'); if(bd) bd.remove();
      renderPolicyHint();
      toast('تم حفظ سياسة الدخول والخروج');
    }).catch(function(){
      if(btn){ btn.disabled=false; btn.textContent='حفظ السياسة'; }
      toast('تعذّر الاتصال بالخادم', true);
    });
  }
  window.GR.savePolicy = savePolicy;

  function initTimePolicy(){
    var hint = q('#arr-time-hint'); if(!hint) return;
    fetch('/api/settings/stay-policy', { credentials:'same-origin', headers:{ 'Accept':'application/json' } })
      .then(function(res){ return res.ok ? res.json() : null; })
      .then(function(body){
        var d = body && body.data;
        POLICY = (d && d.policy) || { checkin_time:'14:00', checkout_time:'12:00' };
        POLICY_CAN_EDIT = !!(d && d.can_edit);
        renderPolicyHint();
      })
      .catch(function(){
        POLICY = { checkin_time:'14:00', checkout_time:'12:00' };
        renderPolicyHint();
      });
  }

  /* ─── 6. VEHICLE + DRIVER ─────────────────────────────────────── */
  var DRIVERS = [];

  function initVehicles(){
    var cars = qq('.ap-car');
    cars.forEach(function(car){
      car.addEventListener('click', function(){
        cars.forEach(function(c){ c.classList.remove('is-on'); c.querySelector('input[type=radio]').checked=false; });
        car.classList.add('is-on'); car.querySelector('input[type=radio]').checked=true;
        var price = (car.querySelector('.cp')||{textContent:''}).textContent.replace(/[^\d]/g,'');
        toast('تم اختيار المركبة · رسوم الاتجاه الواحد: '+price+' ر.س');
      });
    });
    var sw = q('.dr-swap'); if(sw) sw.addEventListener('click', showDriverPicker);
  }

  function showDriverPicker(){
    var rows = DRIVERS.map(function(d,i){
      var ok = d.status==='متاح';
      return '<div style="display:grid;grid-template-columns:48px 1fr auto;gap:12px;align-items:center;padding:12px 14px;border:1px solid var(--hairline);border-radius:10px;margin-bottom:8px">'
        +'<div style="width:48px;height:48px;border-radius:999px;background:linear-gradient(135deg,var(--brand-600),var(--brand-800));color:var(--gold-300);display:grid;place-items:center;font-family:var(--font-ar-display);font-weight:700;font-size:15px">'+d.av+'</div>'
        +'<div><div style="font-weight:600;font-size:14px">'+d.name+'</div>'
          +'<div style="font-size:11px;color:var(--fg-3);margin-top:2px">'+d.car+' · '+d.plate+' · '+d.exp+' · ★ '+d.rate+'</div>'
          +'<div style="font-size:11px;margin-top:3px;color:'+(ok?'var(--success-700)':'var(--warning-700)')+'">● '+d.status+(ok?' · '+d.dist+' من المطار':'')+'</div>'
        +'</div>'
        +(ok?'<button onclick="window.GR.pickDriver('+i+')" style="font-family:var(--font-ar);font-size:12px;padding:8px 16px;border-radius:6px;background:var(--brand-700);color:var(--paper);border:none;cursor:pointer">اختيار</button>'
            :'<span style="font-size:11px;color:var(--fg-3)">غير متاح</span>')
        +'</div>';
    }).join('');
    modal('السائقون المتاحون', rows);
  }

  window.GR.pickDriver = function(i){
    var d=DRIVERS[i], card=q('.dr-card'); if(!card) return;
    card.querySelector('.dr-av').textContent=d.av;
    card.querySelector('.dr-name').textContent=d.name;
    card.querySelector('.dr-meta').innerHTML='<span>سائق معتمد · '+d.exp+'</span><span class="dot">·</span><span class="rate">★ '+d.rate+'</span><span class="dot">·</span><span class="mono">'+d.car+' · '+d.plate+'</span>';
    card.querySelector('.dr-status').innerHTML='<span class="dt"></span>متاح · '+d.dist+' من المطار';
    var m=q('.dh-modal-bd'); if(m)m.remove();
    toast('تم اختيار السائق: '+d.name);
  };

  /* ─── 7. SMS TRIP DETAILS ─────────────────────────────────────── */
  function initSmsTrip(){
    var driver = q('.ap-driver'); if(!driver) return;
    driver.querySelectorAll('.sms-actions button').forEach(function(btn){
      btn.addEventListener('click', function(){
        if(btn.classList.contains('sec')){
          modal('معاينة رسالة تفاصيل الرحلة',
            '<div style="max-width:320px;margin:0 auto 16px">'
            +'<div style="background:var(--ink-900);border-radius:18px;padding:14px;color:var(--paper)">'
              +'<div style="font-family:var(--font-en);font-size:10px;letter-spacing:0.12em;color:var(--gold-300);text-align:center;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.08)">SMS · Dheuof Transport</div>'
              +'<div style="background:rgba(255,255,255,0.06);border-radius:12px;padding:12px 14px;margin-top:10px;display:flex;flex-direction:column;gap:8px">'
                +'<div style="font-size:12px;line-height:1.6;color:var(--ink-50)">مرحباً أحمد، سائقك عبدالرحمن (٤٫٩★) سيستقبلك بصالة الوصول — البوابة ٤، الساعة ١:٢٥م.</div>'
                +'<div style="font-family:var(--font-mono);font-size:11px;color:var(--gold-300);padding:6px 10px;background:rgba(201,168,95,0.12);border:1px dashed rgba(201,168,95,0.35);border-radius:6px;direction:ltr;text-align:left">track.dheuof.sa/t/RIDE-AHM-28</div>'
                +'<div style="font-size:11px;color:var(--ink-200);font-style:italic">Live tracking · driver photo · ETA updates.</div>'
              +'</div>'
              +'<div style="font-size:10px;color:var(--ink-300);text-align:center;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.06)">SMS · 161 chars · مرسل من ٧٠٠٠١</div>'
            +'</div>'
            +'</div>'
            +'<div style="background:var(--brand-50);border:1px solid var(--brand-200);border-radius:10px;padding:14px;font-size:12px">'
              +'<div style="font-weight:700;margin-bottom:8px">💡 كيف يعمل تتبع الرحلة؟</div>'
              +'<div style="color:var(--fg-2);line-height:1.75">١. النزيل يضغط الرابط<br>٢. يرى موقع السائق على الخريطة حياً<br>٣. صورة السائق ولوحة المركبة تظهر له<br>٤. وقت الوصول المتوقع يتحدث آلياً</div>'
            +'</div>'
          );
        } else {
          btn.textContent='✓ تم الإرسال'; btn.style.background='var(--success-600)';
          setTimeout(function(){ btn.textContent='إرسال الآن'; btn.style.background=''; },3500);
          toast('تم إرسال تفاصيل الرحلة للنزيل والسائق ✓');
        }
      });
    });
    qq('.ap-sms-recipients .rcp').forEach(function(rcp){
      rcp.addEventListener('click', function(){
        var cb=rcp.querySelector('input[type=checkbox]'); cb.checked=!cb.checked; rcp.classList.toggle('is-on',cb.checked);
      });
    });
  }

  /* ─── 8 & 9. PAYMENT SYSTEM + SCHEDULE ──────────────────────── */
  function initPayment(){
    qq('.pay-plan').forEach(function(p){
      p.addEventListener('click', function(){
        qq('.pay-plan').forEach(function(x){ x.classList.remove('is-on'); }); p.classList.add('is-on');
        if(p.classList.contains('is-custom')) toast('أضف دفعاتك في جدول الدفعات أدناه');
      });
    });
    qq('.pay-method-row .pm').forEach(function(pm){
      pm.addEventListener('click', function(){
        qq('.pay-method-row .pm').forEach(function(x){ x.classList.remove('is-on'); }); pm.classList.add('is-on');
      });
    });
    qq('.pay-row .x').forEach(function(x){ x.addEventListener('click', function(){ x.closest('.pay-row').remove(); }); });
    qq('.pay-row select').forEach(function(sel){ sel.addEventListener('change', function(){ handleMethod(sel, sel.closest('.pay-row')); }); });

    var addBtn = q('.pay-add'); if(!addBtn) return;
    addBtn.addEventListener('click', function(){
      var n = qq('.pay-rows .pay-row').length+1;
      var ar = ['١','٢','٣','٤','٥','٦','٧','٨','٩','١٠'];
      var row = document.createElement('div'); row.className='pay-row';
      row.innerHTML='<div class="n">'+(ar[n-1]||n)+'</div>'
        +'<div class="gr-field"><label>الوصف</label><input value="دفعة جديدة"/></div>'
        +'<div class="gr-field"><label>الاستحقاق</label><input class="is-mono" placeholder="YYYY-MM-DD" dir="ltr"/></div>'
        +'<div class="gr-field"><label>طريقة الدفع</label><select>'
          +'<option>MADA 💳</option>'
          +'<option>Visa / Mastercard 💳</option>'
          +'<option>Apple Pay </option>'
          +'<option>STC Pay 📱</option>'
          +'<option>نقدي 💵</option>'
          +'<option>تحويل بنكي 🏦</option>'
          +'<option>رابط دفع SMS 📲</option>'
          +'<option>شيك بنكي 📄</option>'
          +'<option>آجل / شركة 🏢</option>'
          +'<option>تخصيص ✏️</option>'
        +'</select></div>'
        +'<div class="gr-field amt"><label>المبلغ (ر.س)</label><input class="is-mono" value="0.00" dir="ltr"/></div>'
        +'<div class="pay-state is-due">معلّقة</div>'
        +'<button class="x">✕</button>';
      q('.pay-rows').appendChild(row);
      row.querySelector('.x').addEventListener('click', function(){ row.remove(); });
      row.querySelector('select').addEventListener('change', function(sel){ return function(){ handleMethod(sel, row); }; }(row.querySelector('select')));
      toast('تمت إضافة دفعة جديدة · غيّر الطريقة إلى "نقدي" لتفعيل حقول الإيصال');
    });
  }

  function handleMethod(sel, row){
    var old = row.querySelector('.cash-note'); if(old) old.remove();
    if((sel.value||'').includes('نقدي')){
      var note = document.createElement('div'); note.className='cash-note';
      note.style.cssText='grid-column:1/-1;background:var(--gold-50);border:1px solid var(--gold-200);border-radius:8px;padding:10px 14px;display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:4px';
      note.innerHTML='<div class="gr-field"><label style="font-size:11px">رقم الإيصال النقدي</label><input placeholder="RC-XXXX" class="is-mono" style="padding:7px 10px;font-size:13px"/></div>'
        +'<div class="gr-field"><label style="font-size:11px">الموظف المستلِم</label><input value="" placeholder="اسم الموظف" style="padding:7px 10px;font-size:13px"/></div>';
      row.appendChild(note);
    }
  }

  /* ─── 10. SMS PAY-LINK ────────────────────────────────────────── */
  function initSmsPayLink(){
    var card = q('.pay-builder .sms-card'); if(!card) return;
    card.querySelectorAll('.sms-actions button').forEach(function(btn){
      btn.addEventListener('click', function(){
        if(btn.classList.contains('sec')){
          modal('معاينة رابط الدفع + كيفية الربط',
            '<div style="max-width:320px;margin:0 auto 16px">'
            +'<div style="background:var(--ink-900);border-radius:18px;padding:14px;color:var(--paper)">'
              +'<div style="font-family:var(--font-en);font-size:10px;letter-spacing:0.12em;color:var(--gold-300);text-align:center;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.08)">رسالة جديدة · Dheuof</div>'
              +'<div style="background:rgba(255,255,255,0.06);border-radius:12px;padding:12px 14px;margin-top:10px;display:flex;flex-direction:column;gap:8px">'
                +'<div style="font-size:12px;line-height:1.6;color:var(--ink-50)">عميلنا العزيز أحمد، رابط دفع آمن للدفعة الثانية (٣٬٠٠٠٫٠٠ ر.س) — فندق الواحة الذهبية:</div>'
                +'<div style="font-family:var(--font-mono);font-size:11px;color:var(--gold-300);padding:6px 10px;background:rgba(201,168,95,0.12);border:1px dashed rgba(201,168,95,0.35);border-radius:6px;direction:ltr;text-align:left">pay.dheuof.sa/r/8KQ2-AHM</div>'
                +'<div style="font-size:11px;color:var(--ink-200);font-style:italic">Secure · valid 48h · powered by Dheuof.</div>'
              +'</div>'
              +'<div style="font-size:10px;color:var(--ink-300);text-align:center;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.06)">SMS · 161 chars · مرسل من ٧٠٠٠١</div>'
            +'</div>'
            +'</div>'
            +'<div style="background:var(--gold-50);border:1px solid var(--gold-200);border-radius:12px;padding:16px;font-size:12px">'
              +'<div style="font-weight:700;font-size:13px;margin-bottom:10px">🔗 كيفية ربط بوابة الدفع</div>'
              +'<div style="display:flex;flex-direction:column;gap:8px;color:var(--fg-2);line-height:1.65">'
                +'<div>① الرابط يُولَّد تلقائياً بواسطة نظام ضيوف لكل دفعة على حدة</div>'
                +'<div>② يقبل: <strong>MADA · Visa · Mastercard · Apple Pay · STC Pay</strong></div>'
                +'<div>③ عند الدفع تُحدَّث حالة الدفعة إلى "مدفوع" تلقائياً في النظام</div>'
                +'<div>④ صلاحية الرابط قابلة للضبط: ٢٤ · ٤٨ · ٧٢ ساعة</div>'
                +'<div style="margin-top:4px;padding:10px;background:var(--brand-50);border-radius:8px;border:1px solid var(--brand-200)">⭐ لتفعيل الربط: تواصل مع فريق ضيوف للاتصال بـ <strong>Moyassar</strong> أو <strong>Telr</strong> أو <strong>HyperPay</strong></div>'
              +'</div>'
            +'</div>'
          );
        } else {
          btn.textContent='✓ تم الإرسال'; btn.style.background='var(--success-600)';
          setTimeout(function(){ btn.textContent='إرسال الآن'; btn.style.background=''; },3500);
          toast('تم إرسال رابط الدفع للنزيل · صالح ٤٨ ساعة ✓');
        }
      });
    });
  }

  /* ─── 11 & 12. CONTRACT + SIGNATURE ──────────────────────────── */
  var clauseN = 4;

  function addDelBtn(cl){
    if(cl.querySelector('.del-cl')) return;
    var btn = document.createElement('button'); btn.className='del-cl';
    btn.textContent='حذف'; btn.style.cssText='margin-inline-start:auto;background:transparent;border:1px solid var(--ink-100);color:var(--fg-3);border-radius:5px;padding:3px 10px;cursor:pointer;font-family:var(--font-ar);font-size:10px';
    btn.addEventListener('click', function(){ if(confirm('حذف هذا البند؟')) cl.remove(); });
    cl.querySelector('.h').appendChild(btn);
  }

  function initContract(){
    qq('.ct-tpl').forEach(function(tpl){
      tpl.addEventListener('click', function(){
        qq('.ct-tpl').forEach(function(t){ t.classList.remove('is-on'); }); tpl.classList.add('is-on');
        var nm = tpl.querySelector('.ttl'); if(nm && !tpl.classList.contains('is-add')) toast('تم تحميل القالب: '+nm.textContent);
      });
    });
    qq('.ct-cl').forEach(addDelBtn);
    var addCl = q('.ct-add'); if(addCl) addCl.addEventListener('click', function(){
      clauseN++;
      var ar=['١','٢','٣','٤','٥','٦','٧','٨','٩','١٠','١١','١٢'];
      var cl=document.createElement('div'); cl.className='ct-cl is-custom';
      cl.innerHTML='<div class="h"><span class="n">'+(ar[clauseN-1]||clauseN)+'</span>'
        +'<input class="ttl-in" value="بند مخصص جديد" placeholder="عنوان البند"/>'
        +'<label class="req-tg"><input type="checkbox"/><span>اختياري</span></label></div>'
        +'<textarea rows="2" placeholder="اكتب نص البند هنا..."></textarea>';
      addCl.before(cl); addDelBtn(cl); cl.querySelector('.ttl-in').focus();
      toast('تمت إضافة البند '+(ar[clauseN-1]||clauseN));
    });

    var side = q('.ct-side'); if(!side) return;
    side.querySelectorAll('.pv-actions .ck-mini').forEach(function(btn){
      btn.addEventListener('click', function(){
        if(btn.textContent.includes('معاينة')) showContractPreview();
        else if(btn.textContent.includes('PDF')) toast('جاري إنشاء ملف PDF...');
        else toast('جاري فتح الطباعة...');
      });
    });
    var signCard = side.querySelector('.sms-card.sign'); if(!signCard) return;
    signCard.querySelectorAll('.sms-actions button').forEach(function(btn){
      btn.addEventListener('click', function(){
        if(btn.classList.contains('sec')) showContractSmsPreview();
        else {
          btn.textContent='✓ تم الإرسال'; btn.style.background='var(--success-600)';
          setTimeout(function(){ btn.textContent='إرسال للتوقيع'; btn.style.background=''; },3500);
          toast('تم إرسال رابط التوقيع الإلكتروني للنزيل ✓');
        }
      });
    });
  }

  function showContractPreview(){
    var clauses = qq('.ct-cl').map(function(cl,i){
      var t=(cl.querySelector('.ttl-in')||{value:''}).value;
      var tx=(cl.querySelector('textarea')||{value:''}).value;
      return '<div style="padding:10px 14px;background:var(--paper-tint);border-radius:8px;border-inline-start:3px solid var(--gold-500);margin-bottom:8px">'
        +'<div style="font-weight:600;font-size:12px;margin-bottom:4px">'+(i+1)+'. '+t+'</div>'
        +'<div style="font-size:12px;color:var(--fg-2);line-height:1.65">'+tx+'</div></div>';
    }).join('');

    modal('معاينة العقد الكامل — مع التوقيع',
      '<div style="background:var(--paper);border:1px solid var(--ink-100);border-radius:10px;padding:24px;max-height:52vh;overflow-y:auto">'
        +'<div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid var(--gold-400)">'
          +'<div><div style="font-family:var(--font-ar-display);font-weight:700;font-size:20px">عقد إقامة فندقية</div>'
            +'<div style="font-family:var(--font-en);font-size:11px;color:var(--fg-3);margin-top:3px">Hotel Stay Agreement · #CT-2025-001872</div></div>'
          +'<div style="text-align:end"><div style="font-family:var(--font-ar-display);font-weight:600">فندق الواحة الذهبية</div>'
            +'<div style="font-family:var(--font-en);font-size:10px;color:var(--fg-3)">Golden Oasis · Riyadh</div></div>'
        +'</div>'
        +'<table style="width:100%;border-collapse:collapse;font-size:12.5px;margin-bottom:16px">'
          +'<tr style="background:var(--paper-tint)"><td style="padding:7px 10px;color:var(--fg-3);width:36%">اسم النزيل</td><td style="padding:7px 10px;font-weight:600" id="contract-name">—</td></tr>'
          +'<tr><td style="padding:7px 10px;color:var(--fg-3)">رقم الهوية</td><td style="padding:7px 10px;font-family:var(--font-mono)" id="contract-id">—</td></tr>'
          +'<tr style="background:var(--paper-tint)"><td style="padding:7px 10px;color:var(--fg-3)">الغرفة</td><td style="padding:7px 10px;font-weight:600" id="contract-room">—</td></tr>'
          +'<tr><td style="padding:7px 10px;color:var(--fg-3)">تاريخ الوصول</td><td style="padding:7px 10px;font-family:var(--font-mono)">2025-05-28</td></tr>'
          +'<tr style="background:var(--paper-tint)"><td style="padding:7px 10px;color:var(--fg-3)">تاريخ المغادرة</td><td style="padding:7px 10px;font-family:var(--font-mono)">2025-05-31</td></tr>'
          +'<tr><td style="padding:7px 10px;color:var(--fg-3)">الإجمالي النهائي</td><td style="padding:7px 10px;font-weight:700;color:var(--gold-800);font-family:var(--font-mono)" id="contract-total">—</td></tr>'
        +'</table>'
        +'<div style="font-weight:600;font-size:13px;margin-bottom:10px">البنود والشروط</div>'
        +clauses
        +'<div style="display:grid;grid-template-columns:1fr 1fr;gap:28px;margin-top:28px;padding-top:16px;border-top:1px solid var(--hairline)">'
          +'<div><div style="font-size:10px;color:var(--fg-3);margin-bottom:8px">توقيع النزيل / Guest Signature</div>'
            +'<div style="font-family:Georgia,serif;font-style:italic;font-size:20px;color:var(--brand-700);padding-bottom:6px;border-bottom:1.5px solid var(--ink-300)" id="contract-signature">—</div>'
            +'<div style="font-size:9px;color:var(--fg-3);margin-top:4px">موقّع إلكترونياً · OTP · 2025-05-28</div>'
          +'</div>'
          +'<div><div style="font-size:10px;color:var(--fg-3);margin-bottom:8px">ختم الفندق / Hotel Seal</div>'
            +'<div style="font-family:var(--font-ar-display);font-size:14px;padding-bottom:6px;border-bottom:1.5px solid var(--ink-300)">فندق الواحة الذهبية</div>'
            +'<div style="font-size:9px;color:var(--fg-3);margin-top:4px">Golden Oasis · CR 1010XXXXXX</div>'
          +'</div>'
        +'</div>'
      +'</div>'
      +'<div style="display:flex;gap:10px;margin-top:14px">'
        +'<button onclick="window.GR.toast(\'جاري إنشاء PDF...\')" style="flex:1;font-family:var(--font-ar);font-size:13px;padding:10px;border-radius:8px;background:var(--white);border:1px solid var(--ink-100);cursor:pointer">↧ PDF</button>'
        +'<button onclick="document.querySelector(\'.dh-modal-bd\').remove()" style="flex:2;font-family:var(--font-ar);font-size:13px;font-weight:600;padding:10px;border-radius:8px;background:var(--brand-700);border:none;cursor:pointer;color:var(--paper)">إغلاق المعاينة</button>'
      +'</div>'
    , true);
  }

  function showContractSmsPreview(){
    modal('معاينة رسالة التوقيع + شرح العملية',
      '<div style="max-width:320px;margin:0 auto 16px">'
      +'<div style="background:var(--ink-900);border-radius:18px;padding:14px;color:var(--paper)">'
        +'<div style="font-family:var(--font-en);font-size:10px;letter-spacing:0.12em;color:var(--gold-300);text-align:center;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.08)">SMS · Dheuof</div>'
        +'<div style="background:rgba(255,255,255,0.06);border-radius:12px;padding:12px 14px;margin-top:10px;display:flex;flex-direction:column;gap:8px">'
          +'<div style="font-size:12px;line-height:1.6;color:var(--ink-50)">عميلنا العزيز أحمد، يُرجى مراجعة وتوقيع عقد إقامتك في فندق الواحة الذهبية:</div>'
          +'<div style="font-family:var(--font-mono);font-size:11px;color:var(--gold-300);padding:6px 10px;background:rgba(201,168,95,0.12);border:1px dashed rgba(201,168,95,0.35);border-radius:6px;direction:ltr;text-align:left">sign.dheuof.sa/c/CT-001872</div>'
          +'<div style="font-size:11px;color:var(--ink-200);font-style:italic">Tap to review · sign · save copy.</div>'
        +'</div>'
      +'</div>'
      +'</div>'
      +'<div style="background:var(--brand-50);border:1px solid var(--brand-200);border-radius:12px;padding:16px;font-size:12px">'
        +'<div style="font-weight:700;font-size:13px;margin-bottom:10px">🔏 كيف يعمل التوقيع الإلكتروني</div>'
        +'<div style="display:flex;flex-direction:column;gap:8px;color:var(--fg-2);line-height:1.65">'
          +'<div>① النزيل يضغط الرابط على هاتفه</div>'
          +'<div>② التحقق بـ OTP على رقم جواله المسجل</div>'
          +'<div>③ مراجعة بنود العقد كاملة قبل التوقيع</div>'
          +'<div>④ يوقّع بأصبعه أو عبر منصة نفاذ</div>'
          +'<div>⑤ يُحفظ PDF موقّع تلقائياً في ملف النزيل</div>'
          +'<div style="margin-top:6px;padding:10px;background:var(--white);border-radius:8px;border:1px solid var(--brand-200)">⭐ للتفعيل: تواصل مع فريق ضيوف للربط مع <strong>نفاذ</strong> أو <strong>DocuSign</strong></div>'
        +'</div>'
      +'</div>'
    );
  }

  /* ─── 13. ID SCANNER SIMULATION ─────────────────────────────── */
  function initScanner(){
    var stage = q('.gr-scan-stage'); if(!stage) return;
    var ic=stage.querySelector('.ic'), body=stage.querySelector('.body'), sub=stage.querySelector('.sub'), ring=stage.querySelector('.ring');
    var scanning=false;

    var info = document.createElement('div');
    info.style.cssText='margin-top:14px;background:rgba(0,0,0,0.2);border-radius:10px;padding:12px 14px;font-size:11px;color:var(--gold-200);line-height:1.8';
    info.innerHTML='<div style="font-weight:600;color:var(--gold-400);margin-bottom:6px">📡 كيف يعمل القارئ</div>'
      +'<div>NFC + OCR + MRZ — يعبّئ ١٢ حقلاً في &lt;٣ ث</div>'
      +'<div>✅ هوية · خليجية · إقامة · جواز سفر</div>'
      +'<div>🔒 البيانات مشفّرة محلياً · لا ترسل للخارج</div>'
      +'<div style="margin-top:6px;color:var(--gold-400);font-size:10px">اضغط هنا للتجربة التوضيحية ▲</div>';
    q('.gr-scan .types').after(info);

    stage.style.cursor='pointer';
    stage.title='اضغط للتجربة التوضيحية';
    stage.addEventListener('click', function(){
      if(scanning) return; scanning=true;
      ring.style.borderColor='rgba(201,168,95,0.9)'; ic.textContent='⚡'; body.textContent='جاري القراءة...'; sub.textContent='Reading NFC / MRZ...';
      setTimeout(function(){ ic.textContent='📊'; body.textContent='معالجة البيانات...'; sub.textContent='Processing · 6 fields...'; },700);
      setTimeout(function(){
        var fid=q('[data-field="idnum"]'), far=q('[data-name="ar"]'), fen=q('[data-name="en"]'), fdob=q('[data-field="dob"]'), fnat=q('[data-field="nationality"]');
        [fid,far,fen,fdob,fnat].forEach(function(el){ if(el){ el.style.transition='background 0.3s'; el.style.background='var(--gold-100)'; el.style.borderColor='var(--gold-500)'; setTimeout(function(){ el.style.background=''; el.style.borderColor=''; },2200); } });
        if(fid)  fid.value='';
        if(far)  far.value='';
        if(fen)  fen.value='';
        if(fdob) fdob.value='';
        if(fnat) fnat.value='';
        var tabs=qq('.gr-id-tab'); tabs.forEach(function(t){ t.classList.remove('is-on'); }); if(tabs[0]) tabs[0].classList.add('is-on');
        ic.textContent='✅'; body.textContent='تمت القراءة!'; sub.textContent='١٢ حقلاً · 0.8s';
        ring.style.borderColor='rgba(74,148,118,0.9)'; stage.style.borderColor='rgba(74,148,118,0.5)';
        toast('قارئ الإثبات: تمت قراءة الهوية وتعبئة ١٢ حقلاً تلقائياً ✓');
        setTimeout(function(){ ic.textContent='📇'; body.textContent='ضع الهوية أو الجواز'; sub.textContent='Insert into the reader'; ring.style.borderColor=''; stage.style.borderColor=''; scanning=false; },4000);
      },1600);
    });
  }

  /* ─── SUBMIT ─────────────────────────────────────────────────── */
  function initSubmit(){
    qq('.gr-foot button').forEach(function(btn){
      btn.addEventListener('click', function(){
        if(btn.textContent.includes('مسوّدة')){ toast('تم حفظ المسوّدة — أكمل التسجيل لاحقاً'); }
        else if(btn.textContent.includes('تسجيل')){
          btn.textContent='⏳ جاري الحفظ...'; btn.disabled=true;
          setTimeout(function(){
            toast('تم تسجيل الدخول · الحجز RES-2025-05-001872 ✓');
            setTimeout(function(){ window.location.href='/static/dheuof/modules/01-guests/index.html'; },1800);
          },1200);
        }
      });
    });
  }

  /* ─── 3. COMPANIONS ──────────────────────────────────────────── */
  function initCompanions(){
    var compList = q('.gr-comp-list');
    if(!compList) return;

    function updateBadge(){
      var badge = document.querySelector('.gr-sec h4 .badge');
      var count = qq('.gr-comp').length;
      if(badge && badge.textContent.indexOf('مرافق')!==-1)
        badge.textContent = count + (count===1?' مرافق':' مرافقين');
    }

    function bindRemove(row){
      var xBtn = row.querySelector('.x');
      if(xBtn) xBtn.addEventListener('click', function(){
        row.remove();
        renumber(); updateBadge();
      });
    }

    function renumber(){
      var ar=['١','٢','٣','٤','٥','٦','٧','٨','٩','١٠'];
      qq('.gr-comp').forEach(function(r,i){ var n=r.querySelector('.n'); if(n) n.textContent=ar[i]||String(i+1); });
    }

    qq('.gr-comp').forEach(bindRemove);

    var addBtn = q('.gr-add-comp');
    if(addBtn) addBtn.addEventListener('click', function(){
      var idx = qq('.gr-comp').length + 1;
      var ar = ['١','٢','٣','٤','٥','٦','٧','٨','٩','١٠'];
      var row = document.createElement('div');
      row.className = 'gr-comp';
      row.innerHTML = '<div class="n">'+(ar[idx-1]||idx)+'</div>'
        +'<div class="gr-field"><label>الاسم الأول</label><input placeholder="الاسم الأول"/></div>'
        +'<div class="gr-field"><label>الاسم الأخير</label><input placeholder="الاسم الأخير"/></div>'
        +'<div class="gr-field"><label>رقم الهوية</label><input class="is-mono" placeholder="اختياري" dir="ltr"/></div>'
        +'<div class="gr-field"><label>رقم الجوال</label><input class="is-mono" placeholder="+966 5X XXX XXXX" dir="ltr"/></div>'
        +'<button class="x">✕</button>';
      compList.appendChild(row);
      bindRemove(row);
      updateBadge();
      toast('تمت إضافة مرافق جديد');
    });
  }

  /* ─── 4. VEHICLE SECTION TOGGLE ──────────────────────────────── */
  function initVehicleToggle(){
    var hidden = localStorage.getItem('veh-section-hidden') === '1';
    if(hidden) _applyVehToggle(true);
  }

  function _applyVehToggle(hide){
    var vehicle = q('.ap-vehicle');
    var driver  = q('.ap-driver');
    var btn     = document.getElementById('veh-toggle-btn');
    if(vehicle){
      var kids = Array.prototype.slice.call(vehicle.children).slice(1);
      kids.forEach(function(el){ el.style.display = hide ? 'none' : ''; });
    }
    if(driver) driver.style.display = hide ? 'none' : '';
    if(btn) btn.textContent = hide ? 'إظهار المركبة والسائق ▼' : 'إخفاء ▲';
  }

  window.toggleVehicleSection = function(){
    var vehicle = q('.ap-vehicle');
    var currently = vehicle && Array.prototype.slice.call(vehicle.children)[1];
    var nowHidden = currently && currently.style.display === 'none';
    _applyVehToggle(!nowHidden);
    localStorage.setItem('veh-section-hidden', nowHidden ? '0' : '1');
    toast(nowHidden ? 'تم إظهار قسم المركبة والسائق' : 'تم إخفاء قسم المركبة والسائق');
  };

  /* ─── INIT ───────────────────────────────────────────────────── */
  function init(){
    initIdTabs(); initNamePriority(); initDates(); initTimePolicy();
    initVehicles(); initSmsTrip(); initPayment(); initSmsPayLink();
    initContract(); initScanner(); initSubmit();
    initCompanions(); initVehicleToggle();
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();

/* ── Room map modal for registration form ── */

// يبني أدوار الخريطة من سجلّ الغرف الحقيقي. الأدوار تُشتق من حقل floor
// في كل غرفة — لا تُكتب يدوياً ولا تُطلب من المستخدم.
window.loadRoomMapFloors = async function(){
  var res, rooms;
  try {
    res = await fetch('/api/rooms', { headers: { 'Accept': 'application/json' } });
    rooms = ((await res.json()) || {}).data || [];
  } catch (e) { return null; }          // فشل الشبكة يُميَّز عن «لا غرف»
  if (!res.ok) return null;

  var TYPE_AR = { standard:'ستاندرد', double:'مزدوجة', twin:'سريران',
                  suite:'جناح', family:'عائلية' };
  var byFloor = {};
  rooms.forEach(function(r){
    var f = (r.floor === null || r.floor === undefined) ? 0 : Number(r.floor);
    (byFloor[f] = byFloor[f] || []).push(r);
  });
  return Object.keys(byFloor).map(Number).sort(function(a,b){ return a-b; })
    .map(function(f){
      var types = {};
      byFloor[f].forEach(function(r){ types[TYPE_AR[r.room_type]||r.room_type||''] = 1; });
      var names = Object.keys(types).filter(Boolean).join(' · ');
      return {
        label: (f === 0 ? 'الدور الأرضي' : 'الدور ' + f) + (names ? ' — ' + names : ''),
        rooms: byFloor[f]
          .sort(function(a,b){
            return String(a.room_number).localeCompare(String(b.room_number),'ar',{numeric:true});
          })
          .map(function(r){ return { num: String(r.room_number), status: r.status || 'available' }; })
      };
    });
};

window.showRoomMapModal = async function(){
  window.__ROOM_MAP_FLOORS = await window.loadRoomMapFloors();
  if (window.__ROOM_MAP_FLOORS === null) {
    window.GR.modal('🏨 خريطة الغرف',
      '<p style="padding:20px;text-align:center;color:var(--danger-700)">تعذّر تحميل الغرف من الخادم.</p>');
    return;
  }
  if (!window.__ROOM_MAP_FLOORS.length) {
    // رابطٌ مباشر لا إرشادٌ نصّي: لوحة التحكم لا يشير إليها شيءٌ من
    // الوحدات، فقولُ «اذهب إلى لوحة التحكم» يترك المستخدم يبحث عن بابٍ
    // لا يراه.
    window.GR.modal('🏨 خريطة الغرف',
      '<div style="padding:24px 20px;text-align:center;line-height:2">'
      + '<div style="font-size:15px;font-weight:600;color:var(--ink-900)">لا غرف مسجَّلة بعد</div>'
      + '<div style="font-size:12.5px;color:var(--fg-3);margin:8px 0 18px">'
      + 'سجّل أدوار منشأتك وغرفها دفعةً واحدة، ثم عُد لاختيار الغرفة.</div>'
      + '<a href="/static/dashboard.html#rooms" target="_blank" '
      + 'style="display:inline-block;background:var(--brand-700);color:#fff;'
      + 'text-decoration:none;padding:10px 22px;border-radius:8px;font-size:13px;'
      + 'font-weight:600;font-family:var(--font-ar)">🏢 افتح تسجيل الأدوار والغرف ←</a>'
      + '</div>');
    return;
  }
  window.__renderRoomMapModal();
};

window.__renderRoomMapModal = function(){
  // الغرف تُحمَّل من سجلّ المنشأة الحقيقي لا من قائمة مكتوبة.
  // كانت هنا ٤٧ غرفةً وهمية (١٠١…٤١٠) تُعرض لكل منشأة مهما كانت غرفها.
  var RFLOORS = window.__ROOM_MAP_FLOORS || [];
  var BG   = {occupied:'#DBEAFE','hk-needed':'#FEF3C7',maintenance:'#FEE2E2',reserved:'#FEF9C3',available:'#DCFCE7',cleaning:'#fae8ff','out-of-order':'#f1f5f9'};
  var LBL  = {occupied:'مشغولة','hk-needed':'تنظيف',maintenance:'صيانة',reserved:'محجوزة',available:'متاحة ✓',cleaning:'تنظيف جارٍ','out-of-order':'خارج الخدمة'};
  var BC   = {occupied:'#93c5fd','hk-needed':'#fcd34d',maintenance:'#fca5a5',reserved:'#fde047',available:'#86efac',cleaning:'#d8b4fe','out-of-order':'#cbd5e1'};

  var html = '<p style="font-size:12px;color:var(--fg-3);margin:0 0 12px">اضغط على غرفة <strong style="color:var(--success-700)">خضراء ✓</strong> لاختيارها مباشرةً في النموذج.</p>';
  html += '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px;font-size:11px">';
  [{k:'available',l:'متاحة'},{k:'occupied',l:'مشغولة'},{k:'hk-needed',l:'تنظيف'},{k:'maintenance',l:'صيانة'},{k:'reserved',l:'محجوزة'},{k:'out-of-order',l:'خارج الخدمة'}].forEach(function(s){
    html+='<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:3px;background:'+BG[s.k]+';border:1px solid '+BC[s.k]+';display:inline-block"></span>'+s.l+'</span>';
  });
  html += '</div>';

  RFLOORS.forEach(function(fl){
    html += '<div style="margin-bottom:14px"><div style="font-size:11px;font-weight:700;color:var(--brand-800);padding:4px 10px;background:var(--brand-50);border-radius:6px;margin-bottom:8px">'+fl.label+'</div>'
      +'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(66px,1fr));gap:5px">';
    fl.rooms.forEach(function(rm){
      var avail = rm.status==='available';
      html += '<div '+(avail?'onclick="window.GR.selectRoom(\''+rm.num+'\')"':'')+' style="background:'+BG[rm.status]+';border:1.5px solid '+BC[rm.status]+';border-radius:8px;padding:8px 4px;text-align:center;cursor:'+(avail?'pointer':'default')+'"'
        +(avail?' title="اضغط لاختيار هذه الغرفة"':'')+' >'
        +'<div style="font-family:monospace;font-size:13px;font-weight:700;color:#111;line-height:1">'+rm.num+'</div>'
        +'<div style="font-size:9px;color:#555;margin-top:3px">'+LBL[rm.status]+'</div>'
        +'</div>';
    });
    html += '</div></div>';
  });

  window.GR.modal('🏨 خريطة الغرف — اختر غرفة متاحة', html);
};

window.GR.modal = function(title, html){
  var bd = document.createElement('div'); bd.className='dh-modal-bd';
  bd.style.cssText='position:fixed;inset:0;background:rgba(14,42,34,0.65);backdrop-filter:blur(4px);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px';
  bd.addEventListener('click',function(e){ if(e.target===bd)bd.remove(); });
  bd.innerHTML='<div dir="rtl" style="background:var(--white);border-radius:16px;width:min(820px,96vw);max-height:88vh;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 24px 64px -16px rgba(14,42,34,0.45)">'
    +'<div style="display:flex;align-items:center;justify-content:space-between;padding:16px 22px;border-bottom:1px solid var(--hairline);background:var(--paper-tint)">'
      +'<div style="font-family:var(--font-ar-display);font-weight:700;font-size:16px;color:var(--ink-900)">'+title+'</div>'
      +'<button onclick="document.querySelector(\'.dh-modal-bd\').remove()" style="background:transparent;border:1px solid var(--ink-100);color:var(--fg-3);border-radius:6px;padding:5px 14px;cursor:pointer;font-family:var(--font-ar);font-size:12px">✕ إغلاق</button>'
    +'</div>'
    +'<div style="padding:20px 22px;overflow-y:auto;direction:rtl">'+html+'</div>'
  +'</div>';
  document.body.appendChild(bd);
};

window.GR.selectRoom = function(num){
  var sel = document.getElementById('room-number-sel');
  if(sel){
    Array.prototype.forEach.call(sel.options, function(opt){
      if(opt.text.indexOf(num) >= 0) sel.value = opt.value;
    });
  }
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  window.GR.toast('تم اختيار الغرفة '+num+' ✓');
};

/* ── URL Params: pre-fill room from checkin.html → rooms view ── */
(function(){
  var params = new URLSearchParams(window.location.search);
  var room = params.get('room'), type = params.get('type');
  if(!room && !type) return;
  setTimeout(function(){
    // Pre-select room type in the stay section
    var typeSelects = document.querySelectorAll('select');
    typeSelects.forEach(function(sel){
      Array.prototype.forEach.call(sel.options, function(opt){
        if(type && opt.text.indexOf(type) >= 0){ sel.value = opt.value; }
      });
    });
    // Pre-fill room number select
    var roomSelects = document.querySelectorAll('select');
    roomSelects.forEach(function(sel){
      Array.prototype.forEach.call(sel.options, function(opt){
        if(room && opt.text.indexOf(room) >= 0){ sel.value = opt.value; }
      });
    });
    // Show banner
    if(room){
      var banner = document.createElement('div');
      banner.style.cssText = 'position:fixed;top:68px;right:50%;transform:translateX(50%);background:var(--brand-700);color:var(--paper);padding:10px 20px;border-radius:8px;font-family:var(--font-ar);font-size:13px;font-weight:600;z-index:999;box-shadow:0 4px 20px rgba(0,0,0,.2)';
      banner.textContent = '🏨 الغرفة ' + room + ' — ' + (type||'') + ' · أدخل بيانات الضيف للمتابعة';
      document.body.appendChild(banner);
      setTimeout(function(){ banner.style.opacity='0'; banner.style.transition='opacity .5s'; setTimeout(function(){ banner.remove(); }, 500); }, 4000);
    }
  }, 200);
})();

/* ══════════════════════════════════════════════════════════════
   TAX ENGINE — ضريبة القيمة المضافة ١٥٪ + ضريبة السياحة ٢٫٥٪
═══════════════════════════════════════════════════════════════ */
(function(){
  // المجموع قبل الضرائب — يُحسب حيّاً من المدخلات في registration-app.js
  // (`window.GR_INV_BASE`)، وإلا رجع إلى الرقم التوضيحي. جعلُه دالةً لا
  // ثابتاً هو ما يجعل الفاتورة تتحدّث مع كل تغيير غرفةٍ أو ليلةٍ أو وجبة.
  function INV_BASE(){
    var b = window.GR_INV_BASE;
    return (typeof b === 'number' && isFinite(b) && b >= 0) ? b : 7740;
  }

  var TAX = {
    vat:     { rate: 0.15,  mode: 'added', labelAr: 'VAT ١٥٪' },
    tourism: { rate: 0.025, mode: 'added', labelAr: 'ضريبة السياحة ٢٫٥٪' }
  };

  function toSAR(n){
    // Format as Arabic numerals with commas
    var s = n.toFixed(2);
    var parts = s.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
    return parts.join('٫')
      .replace(/0/g,'٠').replace(/1/g,'١').replace(/2/g,'٢').replace(/3/g,'٣')
      .replace(/4/g,'٤').replace(/5/g,'٥').replace(/6/g,'٦').replace(/7/g,'٧')
      .replace(/8/g,'٨').replace(/9/g,'٩');
  }

  function getEl(id){ return document.getElementById(id); }

  function syncThumb(checkId, thumbId){
    var cb = getEl(checkId), th = getEl(thumbId); if(!cb||!th) return;
    th.style.right = cb.checked ? '21px' : '3px';
  }

  window.recalcInvoice = function(){
    var vatCb   = getEl('vat-on');
    var tourCb  = getEl('tour-on');
    var vatOn   = vatCb  && vatCb.checked;
    var tourOn  = tourCb && tourCb.checked;

    /* Sync toggle thumb positions */
    syncThumb('vat-on',  'vat-thumb');
    syncThumb('tour-on', 'tour-thumb');

    /* Dim disabled tax rows */
    var vatRow  = getEl('tax-vat-row');
    var tourRow = getEl('tax-tour-row');
    if(vatRow)  vatRow.style.opacity  = vatOn  ? '1' : '0.38';
    if(tourRow) tourRow.style.opacity = tourOn ? '1' : '0.38';

    var vatAmt = 0, tourAmt = 0;

    /* ── VAT ── */
    if(vatOn){
      if(TAX.vat.mode === 'added'){
        vatAmt = INV_BASE() * TAX.vat.rate;
      } else {
        /* شاملة: السعر يتضمن الضريبة، نُظهرها استخلاصاً فقط */
        vatAmt = INV_BASE() - (INV_BASE() / (1 + TAX.vat.rate));
      }
    }

    /* ── السياحة ── */
    if(tourOn){
      if(TAX.tourism.mode === 'added'){
        tourAmt = INV_BASE() * TAX.tourism.rate;
      } else {
        tourAmt = INV_BASE() - (INV_BASE() / (1 + TAX.tourism.rate));
      }
    }

    /* تحديث المبالغ */
    var vatAmtEl  = getEl('vat-amt');
    var tourAmtEl = getEl('tour-amt');
    if(vatAmtEl)  vatAmtEl.textContent  = vatOn  ? toSAR(vatAmt) : '—';
    if(tourAmtEl) tourAmtEl.textContent = tourOn ? toSAR(tourAmt) : '—';

    /* الإجمالي */
    var total = INV_BASE();
    if(vatOn  && TAX.vat.mode  === 'added') total += vatAmt;
    if(tourOn && TAX.tourism.mode === 'added') total += tourAmt;

    var totalEl = getEl('inv-total');
    if(totalEl) totalEl.innerHTML = toSAR(total) + ' <span style="font-size:12px;color:var(--gold-700);font-family:var(--font-ar);font-weight:400">ر.س</span>';

    // يُنشر الإجمالي الرقمي ليقرأه جدول الدفعات (registration-app.js)
    window.GR_INV_TOTAL = total;
    if (typeof window.GR_onInvoiceTotal === 'function') { try { window.GR_onInvoiceTotal(total); } catch(e){} }

    /* ملاحظة الإجمالي */
    var noteEl = getEl('inv-tax-note');
    if(noteEl){
      var parts = [];
      if(vatOn)  parts.push(TAX.vat.mode  === 'added' ? 'مضاف VAT ١٥٪'  : 'شامل VAT ١٥٪');
      if(tourOn) parts.push(TAX.tourism.mode === 'added' ? 'مضافة سياحة ٢٫٥٪' : 'شاملة سياحة ٢٫٥٪');
      if(!parts.length) parts.push('بدون ضرائب — المبلغ صافٍ');
      noteEl.textContent = parts.join(' + ');
    }
  };

  window.toggleTaxMode = function(which){
    var t = TAX[which];
    t.mode = (t.mode === 'added') ? 'inclusive' : 'added';
    var btnId = which === 'vat' ? 'vat-mode-btn' : 'tour-mode-btn';
    var btn = getEl(btnId); if(!btn) return;
    if(t.mode === 'added'){
      btn.textContent = 'مضافة ✦';
      btn.style.borderColor = which === 'vat' ? 'var(--brand-300)' : '#7DD3FC';
      btn.style.background  = which === 'vat' ? 'var(--brand-50)' : '#F0F9FF';
      btn.style.color       = which === 'vat' ? 'var(--brand-700)' : '#0369A1';
    } else {
      btn.textContent = 'شاملة ◉';
      btn.style.borderColor = '#86EFAC';
      btn.style.background  = '#F0FDF4';
      btn.style.color       = '#15803D';
    }
    window.recalcInvoice();
  };

  /* تهيئة أولية لمزامنة أزرار التبديل */
  document.addEventListener('DOMContentLoaded', function(){
    syncThumb('vat-on',  'vat-thumb');
    syncThumb('tour-on', 'tour-thumb');
  });

})();

/* ══════════════════════════════════════════════════════════════
   PAYMENT METHODS — متعددة وقابلة للتخصيص
═══════════════════════════════════════════════════════════════ */
(function(){

  window.togglePayMethod = function(btn){
    btn.classList.toggle('is-on');
    updateMethodSummary();
  };

  function updateMethodSummary(){
    var btns = document.querySelectorAll('#pmm-grid .pmm-btn:not(.pmm-add-btn)');
    var active = [];
    btns.forEach(function(b){ if(b.classList.contains('is-on')) active.push(b.dataset.method); });
    var list = document.getElementById('pmm-active-list');
    if(list) list.textContent = active.length ? active.join(' · ') : 'لا توجد طريقة دفع مختارة';
  }

  window.addCustomPayMethod = function(){
    var name = prompt('اسم طريقة الدفع الجديدة (مثال: Tabby · مدى الإنترنت · بطاقة هدية):');
    if(!name || !name.trim()) return;
    name = name.trim();
    var grid = document.getElementById('pmm-grid'); if(!grid) return;
    var addBtn = grid.querySelector('.pmm-add-btn');
    var btn = document.createElement('button');
    btn.className = 'pmm-btn is-on';
    btn.dataset.method = name;
    btn.onclick = function(){ window.togglePayMethod(btn); };
    btn.innerHTML = '<span>✏️</span> ' + name;
    grid.insertBefore(btn, addBtn);
    updateMethodSummary();
  };

  /* تهيئة أولية */
  document.addEventListener('DOMContentLoaded', function(){
    updateMethodSummary();
  });

})();
