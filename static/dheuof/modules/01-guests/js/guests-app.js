// guests-app.js — منطق وحدة النزلاء والحجوزات
//
// مُستخرَج من index.html كما هو، بلا تفكيك: المنطق كلّه داخل غلافٍ
// واحد `(function(){…})()`، فتقسيمه إلى ملفات منفصلة يقطع كل مرجع
// بين أجزائه. تقسيمه يحتاج تحويله إلى وحدات ES باستيرادات صريحة،
// وهو تغييرٌ يستحق مراجعةً على حدة.
//
// ما فيه: التبويبات · الحجوزات · النزلاء · خريطة الغرف (من /api/rooms)
//         · حسابات الموظفين (من /api/staff/accounts)

(function(){
'use strict';

/* ═══════════════════════════════════════════════
   DATA — all dates relative to today 2026-05-30
═══════════════════════════════════════════════ */

var RESERVATIONS = [];

var GUESTS = [];

var FLOORS = [];

var STAFF = [];

var staffCounter = 7;
var alertCounter = 100;

/* ═══════════════════════════════════════════════
   ROLE → PERMISSIONS MAP
═══════════════════════════════════════════════ */
var ALL_PROGRAMS = ["01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16"];
var ROLE_PERMS = {
  manager:      ["01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16"],
  reception:    ["01","02","06","08"],
  housekeeping: ["01","04"],
  maintenance:  ["04","05"],
  accounting:   ["06","07","11"],
  custom:       [],
};
var currentRole = "reception";

/* ═══════════════════════════════════════════════
   UTILITIES
═══════════════════════════════════════════════ */
function toast(msg, isErr){
  var old = document.querySelector('.dh-toast'); if(old) old.remove();
  var t = document.createElement('div'); t.className='dh-toast';
  t.style.background = isErr ? 'var(--danger-700)' : 'var(--brand-800)';
  t.innerHTML = '<span style="color:var(--gold-400)">'+(isErr?'✕':'✓')+'</span> '+msg;
  document.body.appendChild(t);
  setTimeout(function(){ t.style.opacity='0'; t.style.transition='opacity .4s'; setTimeout(function(){ if(t.parentNode)t.remove(); },400); },3200);
}

function modal(title, html, footHtml){
  var old = document.querySelector('.dh-modal-bd'); if(old) old.remove();
  var bd = document.createElement('div'); bd.className='dh-modal-bd';
  bd.addEventListener('click',function(e){ if(e.target===bd) bd.remove(); });
  bd.innerHTML = '<div class="dh-modal" dir="rtl">'
    +'<div class="modal-head"><div class="ttl">'+title+'</div>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">✕ إغلاق</button></div>'
    +'<div class="modal-body">'+html+'</div>'
    +(footHtml?'<div class="modal-foot">'+footHtml+'</div>':'')
    +'</div>';
  document.body.appendChild(bd);
}

function todayStr(){ return new Date().toISOString().split('T')[0]; }
function tomorrowStr(){ return new Date(Date.now()+86400000).toISOString().split('T')[0]; }
function weekEndStr(){ return new Date(Date.now()+7*86400000).toISOString().split('T')[0]; }

/* ═══════════════════════════════════════════════
   TABS
═══════════════════════════════════════════════ */
document.querySelectorAll('.tab-btn').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('.tab-btn').forEach(function(b){ b.classList.remove('is-on'); });
    document.querySelectorAll('.tab-pane').forEach(function(p){ p.classList.remove('is-on'); });
    btn.classList.add('is-on');
    var pane = document.getElementById('tab-'+btn.dataset.tab);
    if(pane) pane.classList.add('is-on');
    // تُحمَّل الخريطة عند فتح تبويبها لا عند فتح الصفحة: تحميلُ ما لا
    // يُنظَر إليه يُبطئ أول عرض بلا فائدة.
    if(btn.dataset.tab === 'rooms' && !FLOORS.length) loadRoomMap();
    if(btn.dataset.tab === 'reception' && !STAFF.length) loadStaffAccountsFromServer();
  });
});

/* ═══════════════════════════════════════════════
   TAB 1 — RESERVATIONS
═══════════════════════════════════════════════ */
var activeResFilter = 'all';

function renderReservations(list){
  var tbody = document.getElementById('res-tbody');
  if(!tbody) return;
  if(!list.length){
    tbody.innerHTML='<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--fg-3)">لا توجد حجوزات تطابق البحث</td></tr>';
    return;
  }
  tbody.innerHTML = list.map(function(r){
    var payPill = '<span class="pill '+r.payClass+'"><span class="d"></span>'+r.payment+'</span>';
    var vipTag = r.vip ? '<span class="vip-tag">VIP</span>' : '';
    var rid = r.id;
    return '<tr>'
      +'<td><span style="font-family:var(--font-en);font-size:12px;color:var(--fg-3)">'+rid+'</span></td>'
      +'<td><div class="guest-cell"><div class="av'+(r.vip?' vip':'')+'">'+r.initials+'</div><div>'
        +'<div class="name">'+r.name+vipTag+'</div>'
        +'<div class="meta">'+r.nationality+' · '+r.idType+'</div>'
      +'</div></div></td>'
      +'<td><span style="font-family:var(--font-mono);font-size:11px;color:var(--fg-2)">'+r.idNum+'</span></td>'
      +'<td><div style="font-weight:600">'+r.room+'</div><div style="font-size:11px;color:var(--fg-3)">'+r.roomType+'</div></td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+r.checkin+'</td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+r.checkout+'</td>'
      +'<td style="text-align:center"><span style="font-family:var(--font-en);font-weight:600">'+r.nights+'</span> <span style="font-size:11px;color:var(--fg-3)">ليلة</span></td>'
      +'<td><span style="font-size:12px">'+r.channel+'</span></td>'
      +'<td>'+payPill+'</td>'
      +'<td class="amt">'+r.amt+'<span class="cur">ر.س</span></td>'
      +'<td><button class="checkin-btn" id="ci-'+rid+'" onclick="doCheckin(this)">تسجيل دخول</button></td>'
      +'<td><button class="icon-btn" onclick="showResDetail('+JSON.stringify(rid)+')"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="1"/><circle cx="12" cy="5" r="1"/><circle cx="12" cy="19" r="1"/></svg></button></td>'
      +'</tr>';
  }).join('');
}

function filterAndRenderRes(){
  var q = ((document.getElementById('res-search')||{}).value||'').toLowerCase();
  var today = todayStr(), tomorrow = tomorrowStr(), weekEnd = weekEndStr();
  var filtered = RESERVATIONS.filter(function(r){
    var mQ = !q || r.name.toLowerCase().includes(q) || r.id.includes(q) || r.room.includes(q) || r.idNum.toLowerCase().includes(q);
    var mF = activeResFilter==='all'
      || (activeResFilter==='today'    && r.checkin===today)
      || (activeResFilter==='tomorrow' && r.checkin===tomorrow)
      || (activeResFilter==='week'     && r.checkin>=today && r.checkin<=weekEnd);
    return mQ && mF;
  });
  renderReservations(filtered);
}

document.querySelectorAll('[data-filter]').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('[data-filter]').forEach(function(b){ b.classList.remove('is-on'); });
    btn.classList.add('is-on');
    activeResFilter = btn.dataset.filter;
    filterAndRenderRes();
  });
});
var resSearch = document.getElementById('res-search');
if(resSearch) resSearch.addEventListener('input', filterAndRenderRes);

window.showResDetail = function(rid){
  var r = RESERVATIONS.find(function(x){ return x.id===rid; });
  if(!r) return;
  var html = [
    {l:'اسم النزيل',v:r.name+(r.vip?' <span class="vip-tag">VIP</span>':'')},
    {l:'رقم الهوية',v:'<span style="font-family:var(--font-mono)">'+r.idNum+'</span>'},
    {l:'نوع الهوية',v:r.idType},
    {l:'الجنسية',v:r.nationality},
    {l:'الجوال',v:'<span style="direction:ltr;font-family:var(--font-mono)">'+r.phone+'</span>'},
    {l:'الغرفة',v:r.room+' — '+r.roomType},
    {l:'تاريخ الوصول',v:'<span style="font-family:var(--font-mono)">'+r.checkin+'</span>'},
    {l:'تاريخ المغادرة',v:'<span style="font-family:var(--font-mono)">'+r.checkout+'</span>'},
    {l:'عدد الليالي',v:r.nights+' ليالٍ'},
    {l:'القناة',v:r.channel},
    {l:'المبلغ',v:r.amt+' ر.س'},
    {l:'حالة الدفع',v:r.payment},
    {l:'نقاط الولاء',v:'<span style="color:var(--gold-500);font-weight:700;font-family:var(--font-en)">★ 1,240</span> نقطة · مستوى ذهبي'},
  ].map(function(row){ return '<div class="detail-row"><span class="lbl">'+row.l+'</span><span class="val">'+row.v+'</span></div>'; }).join('');
  modal('تفاصيل الحجز — '+rid, html,
    '<button class="btn-primary" onclick="var b=document.getElementById(\'ci-'+rid+'\');if(b)doCheckin(b);document.querySelector(\'.dh-modal-bd\').remove()">تسجيل دخول الآن</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إغلاق</button>'
  );
};

/* ═══════════════════════════════════════════════
   TAB 2 — GUESTS
═══════════════════════════════════════════════ */
var activeGuestFilter = 'all';

function renderGuestAlerts(gid, alerts){
  return '<div class="alert-list" id="alr-'+gid+'">'
    + alerts.map(function(a){
        return '<span class="alert-tag '+a.color+'" onclick="removeAlert('+JSON.stringify(gid)+','+a.id+')">'
          +a.text+' <span class="x">✕</span></span>';
      }).join('')
    +'<button class="add-alert-btn" onclick="showAddAlert('+JSON.stringify(gid)+')">+ تنبيه</button>'
    +'</div>';
}

function renderGuests(list){
  var tbody = document.getElementById('guest-tbody');
  if(!tbody) return;
  if(!list.length){
    tbody.innerHTML='<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--fg-3)">لا يوجد نزلاء يطابقون البحث</td></tr>';
    return;
  }
  var statusMap = {
    ok:        '<span class="pill info"><span class="d"></span>مقيم</span>',
    departing: '<span class="pill warn"><span class="d"></span>مغادر اليوم</span>',
  };
  tbody.innerHTML = list.map(function(g){
    var vipTag = g.vip ? '<span class="vip-tag">VIP</span>' : '';
    var balance = g.balanceLeft==='٠'
      ? '<span style="color:var(--success-700);font-weight:600">مسدَّد</span>'
      : '<span class="amt">'+g.balanceLeft+'<span class="cur">ر.س</span></span>';
    var checkoutBtn = g.status==='departing'
      ? '<button class="icon-btn" style="color:var(--warning-700)" onclick="doCheckout('+JSON.stringify(g.id)+')" title="تسجيل خروج">'
        +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg></button>'
      : '';
    return '<tr>'
      +'<td><div class="guest-cell"><div class="av'+(g.vip?' vip':'')+'">'+g.initials+'</div><div>'
        +'<div class="name">'+g.name+vipTag+'</div>'
        +'<div class="meta">'+g.nationality+'</div>'
      +'</div></div></td>'
      +'<td><div style="font-weight:600">'+g.room+'</div><div style="font-size:11px;color:var(--fg-3)">'+g.roomType+'</div></td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+g.checkin+'</td>'
      +'<td style="font-family:var(--font-mono);font-size:12px">'+g.checkout+'</td>'
      +'<td style="direction:ltr;font-family:var(--font-mono);font-size:12px;color:var(--fg-2)">'+g.phone+'</td>'
      +'<td>'+balance+'</td>'
      +'<td>'+renderGuestAlerts(g.id, g.alerts)+'</td>'
      +'<td>'+statusMap[g.status]+'</td>'
      +'<td>'
        +'<button class="icon-btn" onclick="showGuestDetail('+JSON.stringify(g.id)+')" title="تفاصيل">'
          +'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>'
        +'</button>'
        +checkoutBtn
      +'</td>'
      +'</tr>';
  }).join('');
}

function filterAndRenderGuests(){
  var q = ((document.getElementById('guest-search')||{}).value||'').toLowerCase();
  var filtered = GUESTS.filter(function(g){
    var mQ = !q || g.name.toLowerCase().includes(q) || g.room.includes(q);
    var mF = activeGuestFilter==='all'
      || (activeGuestFilter==='vip'      && g.vip)
      || (activeGuestFilter==='departing'&& g.status==='departing')
      || (activeGuestFilter==='alert'    && g.alerts.length>0);
    return mQ && mF;
  });
  renderGuests(filtered);
}

document.querySelectorAll('[data-gfilter]').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('[data-gfilter]').forEach(function(b){ b.classList.remove('is-on'); });
    btn.classList.add('is-on');
    activeGuestFilter = btn.dataset.gfilter;
    filterAndRenderGuests();
  });
});
var guestSearch = document.getElementById('guest-search');
if(guestSearch) guestSearch.addEventListener('input', filterAndRenderGuests);

window.removeAlert = function(gid, aid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  g.alerts = g.alerts.filter(function(a){ return a.id!==aid; });
  var wrap = document.getElementById('alr-'+gid);
  if(wrap) wrap.outerHTML = renderGuestAlerts(gid, g.alerts);
  updateBadges();
};

window.showAddAlert = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  var colors = [
    {key:'red',  bg:'#fef2f2', label:'طارئ'},
    {key:'amber',bg:'#fffbeb', label:'تنبيه'},
    {key:'blue', bg:'#eff6ff', label:'معلومة'},
    {key:'gold', bg:'#fefce8', label:'طلب'},
    {key:'green',bg:'#f0fdf4', label:'إيجابي'},
  ];
  window._alertColor = 'amber';
  var html = '<div class="alert-form">'
    +'<div><label>نص التنبيه</label>'
    +'<input id="alert-txt" placeholder="مثال: يطلب فطور الساعة ٨، حساسية من..."/></div>'
    +'<div><label>اللون</label><div class="color-opts">'
    +colors.map(function(c,i){
      return '<div class="color-opt'+(i===1?' is-on':'')+'" style="background:'+c.bg+'" title="'+c.label+'" onclick="selectAlertColor(this,\''+c.key+'\')"></div>';
    }).join('')
    +'</div></div></div>';
  modal('إضافة تنبيه — '+g.name, html,
    '<button class="btn-primary" onclick="saveAlert('+JSON.stringify(gid)+')">حفظ</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إلغاء</button>'
  );
};

window.selectAlertColor = function(el, key){
  document.querySelectorAll('.color-opt').forEach(function(c){ c.classList.remove('is-on'); });
  el.classList.add('is-on');
  window._alertColor = key;
};

window.saveAlert = function(gid){
  var inp = document.getElementById('alert-txt');
  var txt = inp ? inp.value.trim() : '';
  if(!txt){ toast('أدخل نص التنبيه',true); return; }
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  alertCounter++;
  g.alerts.push({text:txt, color:window._alertColor||'amber', id:alertCounter});
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  filterAndRenderGuests();
  updateBadges();
  toast('تم إضافة التنبيه ✓');
};

window.showGuestDetail = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  var html = [
    {l:'الاسم',    v:g.name+(g.vip?' <span class="vip-tag">VIP</span>':'')},
    {l:'الغرفة',   v:g.room+' — '+g.roomType},
    {l:'الوصول',   v:'<span style="font-family:var(--font-mono)">'+g.checkin+'</span>'},
    {l:'المغادرة', v:'<span style="font-family:var(--font-mono)">'+g.checkout+'</span>'},
    {l:'الجوال',   v:'<span style="direction:ltr;font-family:var(--font-mono)">'+g.phone+'</span>'},
    {l:'المبلغ المتبقي',v:g.balanceLeft+' ر.س'},
    {l:'التنبيهات', v:g.alerts.length ? g.alerts.map(function(a){return a.text;}).join(' · ') : 'لا يوجد'},
    {l:'نقاط الولاء',v:'<span style="color:var(--gold-500);font-weight:700;font-family:var(--font-en)">★ 1,240</span> نقطة · مستوى ذهبي'},
  ].map(function(row){ return '<div class="detail-row"><span class="lbl">'+row.l+'</span><span class="val">'+row.v+'</span></div>'; }).join('');
  modal('ملف النزيل — '+g.name, html);
};

/* ═══════════════════════════════════════════════
   تحميل خريطة الغرف من سجلّ الغرف الحقيقي

   كانت FLOORS مصفوفةً فارغة لا يملؤها شيء، فالخريطة تُرسم خاويةً مهما
   سجّل المشترك من غرف. وسجلّ الغرف (/api/rooms) كان يعيش في اللوحة
   الرئيسية وحدها — تطبيقان لا يريان بعضهما.

   الأدوار تُشتق من حقل floor في كل غرفة: لا يُطلب عددها من المستخدم
   لأن رقم الدور مُسجَّل مع كل غرفة أصلاً، وطلبُه مرتين يفتح باب
   التناقض بينهما.
═══════════════════════════════════════════════ */
// اللون والتسمية من الخادم (services/room_status) — مصدرٌ واحد. هذه نسخةٌ
// احتياطية لو غاب حقل الخادم فقط، لا مصدرٌ ثانٍ يتباعد عنه.
var ROOM_STATUS_FALLBACK = {
  available:  {label:'جاهزة',  hex:'#16a34a'},
  occupied:   {label:'مشغولة', hex:'#b45309'},
  cleaning:   {label:'نظافة',  hex:'#2563eb'},
  maintenance:{label:'صيانة',  hex:'#dc2626'},
  renovation: {label:'ترميم',  hex:'#6b7280'}
};

function floorLabel(n){
  if(n === 0) return 'الدور الأرضي';
  if(n === -1) return 'القبو';
  return 'الدور ' + n;
}

function buildFloorsFromRooms(rooms){
  var byFloor = {};
  rooms.forEach(function(r){
    var f = (r.floor === null || r.floor === undefined) ? 0 : Number(r.floor);
    var st = r.status || 'available';
    var fb = ROOM_STATUS_FALLBACK[st] || ROOM_STATUS_FALLBACK.available;
    (byFloor[f] = byFloor[f] || []).push({
      num: r.room_number,
      type: r.room_type || '—',
      status: st,                                   // حالة الخادم المعتمدة
      statusLabel: r.status_label || fb.label,      // التسمية من الخادم
      statusHex: r.status_hex || fb.hex,            // اللون من الخادم
      guest: null,
      checkin: null,
      id: r.id
    });
  });
  return Object.keys(byFloor)
    .map(Number)
    .sort(function(a, b){ return a - b; })
    .map(function(f){
      return {
        num: f,
        label: floorLabel(f),
        rooms: byFloor[f].sort(function(a, b){
          return String(a.num).localeCompare(String(b.num), 'ar', {numeric:true});
        })
      };
    });
}

function loadRoomMap(){
  var c = document.getElementById('floors-container');
  if(c && !FLOORS.length){
    c.innerHTML = '<div class="mod-empty" style="padding:24px;text-align:center">⏳ جارٍ تحميل خريطة الغرف…</div>';
  }
  return fetch('/api/rooms')
    .then(function(r){ return r.json(); })
    .then(function(res){
      var rooms = (res && res.data) || [];
      FLOORS = buildFloorsFromRooms(rooms);
      // كل دور مفتوح افتراضياً — الخريطة تُقرأ دفعةً واحدة عادةً
      floorOpen = FLOORS.map(function(){ return true; });
      if(!FLOORS.length && c){
        c.innerHTML = '<div class="mod-empty" style="padding:24px;text-align:center">'
          + 'لا غرف مسجَّلة بعد — سجّلها من «حالة الغرف» في لوحة التحكم</div>';
        return;
      }
      renderFloors();
      updateBadges();
    })
    .catch(function(){
      if(c) c.innerHTML = '<div class="mod-empty" style="padding:24px;text-align:center;color:#b91c1c">'
        + 'تعذّر تحميل خريطة الغرف</div>';
    });
}

/* ═══════════════════════════════════════════════
   TAB 3 — ROOMS
═══════════════════════════════════════════════ */
var floorOpen = [];   // يُبنى من عدد الأدوار الفعلي عند التحميل

function statusLabel(s){
  var fb = ROOM_STATUS_FALLBACK[s];
  if(fb) return fb.label;
  // مسمّياتٌ قديمة قد ترد من مسارات أخرى
  return {'hk-needed':'نظافة',reserved:'محجوزة','out-of-order':'ترميم',dirty:'نظافة',blocked:'ترميم'}[s]||s;
}
function statusHex(s){ return (ROOM_STATUS_FALLBACK[s]||ROOM_STATUS_FALLBACK.available).hex; }

function renderFloors(){
  var c = document.getElementById('floors-container');
  if(!c) return;
  c.innerHTML='';
  FLOORS.forEach(function(fl,fi){
    var occ  = fl.rooms.filter(function(r){return r.status==='occupied';}).length;
    var avl  = fl.rooms.filter(function(r){return r.status==='available';}).length;
    var hk   = fl.rooms.filter(function(r){return r.status==='cleaning';}).length;
    var mnt  = fl.rooms.filter(function(r){return r.status==='maintenance';}).length;
    var sec  = document.createElement('div'); sec.className='floor-section';
    var head = '<div class="floor-head" onclick="toggleFloor('+fi+')">'
      +'<span class="floor-num">'+fl.num+'</span>'
      +'<span class="floor-name">'+fl.label+'</span>'
      +'<div class="floor-stats">'
      +(occ  ?'<span class="floor-stat occ">'+occ+' مشغولة</span>':'')
      +(avl  ?'<span class="floor-stat avail">'+avl+' متاحة</span>':'')
      +(hk   ?'<span class="floor-stat hk">'+hk+' تنظيف</span>':'')
      +(mnt  ?'<span class="floor-stat maint">'+mnt+' صيانة</span>':'')
      +'</div>'
      +'<span class="floor-toggle'+(floorOpen[fi]?' open':'')+'">▼</span>'
      +'</div>';
    var grid = '<div class="rooms-grid" id="fg-'+fi+'" style="'+(floorOpen[fi]?'':'display:none')+'">'
      +fl.rooms.map(function(rm,ri){
        var hint = rm.guest
          ? '<div class="guest-hint">'+rm.guest+'</div>'
          : (rm.checkin?'<div class="guest-hint">وصول '+rm.checkin+'</div>':'');
        // اللون من الخادم مباشرةً: حدٌّ ملوّن وخلفيةٌ خفيفة، فتظهر الحالات
        // الخمس بألوانها (أخضر/ذهبي/أزرق/أحمر/رمادي) بلا اعتمادٍ على أصناف CSS.
        var hex = rm.statusHex || statusHex(rm.status);
        var lbl = rm.statusLabel || statusLabel(rm.status);
        return '<div class="room-card '+rm.status+'" onclick="showRoomDetail('+fi+','+ri+')" title="غرفة '+rm.num+'"'
          +' style="border-right:4px solid '+hex+';box-shadow:inset 0 0 0 1px '+hex+'22">'
          +'<div class="rnum">'+rm.num+'</div>'
          +'<div class="rtype">'+rm.type+'</div>'
          +'<div class="rstatus" style="color:'+hex+';font-weight:600">'+lbl+'</div>'
          +hint
          +'</div>';
      }).join('')
      +'</div>';
    sec.innerHTML = head + grid;
    c.appendChild(sec);
  });
}

window.toggleFloor = function(fi){
  floorOpen[fi] = !floorOpen[fi];
  var grid = document.getElementById('fg-'+fi);
  var tog  = document.querySelector('.floor-section:nth-child('+(fi+1)+') .floor-toggle');
  if(grid) grid.style.display = floorOpen[fi] ? '' : 'none';
  if(tog)  tog.classList.toggle('open', floorOpen[fi]);
};

window.showRoomDetail = function(fi,ri){
  var rm = FLOORS[fi].rooms[ri];
  var fl = FLOORS[fi];
  var sc = {occupied:'info',available:'ok',cleaning:'warn',maintenance:'danger',renovation:'gold'};
  var html = [
    {l:'رقم الغرفة', v:'<span style="font-family:var(--font-en);font-size:18px;font-weight:700">'+rm.num+'</span>'},
    {l:'نوع الغرفة', v:rm.type},
    {l:'الدور',      v:fl.label},
    {l:'الحالة',     v:'<span class="pill '+sc[rm.status]+'"><span class="d"></span>'+statusLabel(rm.status)+'</span>'},
  ].map(function(row){ return '<div class="detail-row"><span class="lbl">'+row.l+'</span><span class="val">'+row.v+'</span></div>'; });
  if(rm.guest)    html.push('<div class="detail-row"><span class="lbl">النزيل</span><span class="val">'+rm.guest+'</span></div>');
  if(rm.checkout) html.push('<div class="detail-row"><span class="lbl">تاريخ المغادرة</span><span class="val" style="font-family:var(--font-mono)">'+rm.checkout+'</span></div>');
  if(rm.checkin)  html.push('<div class="detail-row"><span class="lbl">تاريخ الوصول</span><span class="val" style="font-family:var(--font-mono)">'+rm.checkin+'</span></div>');

  var statusOptions = [
    {val:'available',   label:'🟢 جاهزة'},
    {val:'occupied',    label:'🟡 مشغولة'},
    {val:'cleaning',    label:'🔵 نظافة'},
    {val:'maintenance', label:'🔴 صيانة'},
    {val:'renovation',  label:'⚪ ترميم'}
  ];
  var act = '<select id="rm-status-sel" style="flex:1;padding:7px 12px;border:1px solid var(--ink-100);border-radius:6px;font-family:var(--font-ar);font-size:13px">'
    +statusOptions.map(function(s){ return '<option value="'+s.val+'"'+(rm.status===s.val?' selected':'')+'>'+s.label+'</option>'; }).join('')
    +'</select>'
    +'<button class="btn-primary" onclick="changeRoomStatus('+fi+','+ri+')">✓ تغيير الحالة</button>'
    +'<button class="close-btn" onclick="document.querySelector(\'.dh-modal-bd\').remove()">إغلاق</button>';

  modal('غرفة '+rm.num+' — '+statusLabel(rm.status), html.join(''), act);
};

window.markRoomClean = function(fi,ri){
  var num = FLOORS[fi].rooms[ri].num;
  FLOORS[fi].rooms[ri].status = 'available';
  FLOORS[fi].rooms[ri].guest  = null;
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  renderFloors(); updateBadges();
  toast('غرفة '+num+' — تم التحويل إلى متاحة ✓');
};

window.markRoomMaint = function(fi,ri){
  var num = FLOORS[fi].rooms[ri].num;
  FLOORS[fi].rooms[ri].status = 'maintenance';
  var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
  renderFloors(); updateBadges();
  toast('غرفة '+num+' — تم التحويل إلى صيانة');
};

window.changeRoomStatus = function(fi,ri){
  var sel = document.getElementById('rm-status-sel');
  if(!sel) return;
  var room = FLOORS[fi].rooms[ri];
  var newStatus = sel.value, num = room.num;
  // يُحفَظ في الخادم فعلاً — لا تغييرٌ في الذاكرة يدّعي النجاح. الخادم
  // يفرض صلاحية الكتابة (مالك/مدير المنشأة) ويردّ ٤٠٣ لمن لا يملكها.
  if(!room.id){ toast('غرفة غير معرّفة في السجل', true); return; }
  fetch('/api/rooms/'+room.id+'/status', {
    method:'PATCH', credentials:'same-origin',
    headers:{'Content-Type':'application/json','Accept':'application/json'},
    body: JSON.stringify({status:newStatus})
  }).then(function(res){
    return res.json().catch(function(){return {};}).then(function(b){return {ok:res.ok,b:b};});
  }).then(function(r){
    if(!r.ok){ toast((r.b&&(r.b.detail||r.b.error))||'تعذّر تغيير الحالة', true); return; }
    room.status = newStatus;
    room.statusLabel = statusLabel(newStatus);
    room.statusHex = statusHex(newStatus);
    if(newStatus==='available'||newStatus==='renovation') room.guest = null;
    var bd = document.querySelector('.dh-modal-bd'); if(bd) bd.remove();
    renderFloors(); updateBadges();
    toast('غرفة '+num+' — '+statusLabel(newStatus)+' ✓');
  }).catch(function(){ toast('تعذّر الاتصال بالخادم', true); });
};

/* ═══════════════════════════════════════════════
   BADGES & KPIs
═══════════════════════════════════════════════ */
function updateBadges(){
  var hkCount = 0;
  FLOORS.forEach(function(fl){ fl.rooms.forEach(function(rm){ if(rm.status==='cleaning') hkCount++; }); });
  var totalRooms = 0;
  var occCount   = 0;
  FLOORS.forEach(function(fl){
    fl.rooms.forEach(function(rm){
      totalRooms++;
      if(rm.status==='occupied') occCount++;
    });
  });
  var occPct = totalRooms>0 ? Math.round(occCount/totalRooms*100) : 0;

  function set(id,v){ var el=document.getElementById(id); if(el) el.textContent=v; }
  set('kpi-occ', occPct);
  set('kpi-inhouse',   GUESTS.length);
  set('kpi-upcoming',  RESERVATIONS.length);
  set('kpi-hk',        hkCount);
  set('kpi-inhouse-delta', GUESTS.filter(function(g){return g.status==='departing';}).length+' مغادر اليوم');
  set('kpi-upcoming-delta', RESERVATIONS.filter(function(r){return r.payment==='لم يدفع';}).length+' لم يدفع بعد');

  var hkD = document.getElementById('kpi-hk-delta');
  if(hkD){ hkD.textContent = hkCount>0 ? 'تحتاج تنظيف' : 'جميع الغرف نظيفة ✓'; hkD.style.color=hkCount>0?'var(--warning-700)':'var(--success-700)'; }

  set('res-badge',    RESERVATIONS.length);
  set('guests-badge', GUESTS.length);
  set('rooms-badge',  hkCount+' HK');
  set('staff-badge',  STAFF.filter(function(s){return s.active;}).length);
}

/* ═══════════════════════════════════════════════
   API — LOAD GUESTS (GET /api/guests)
═══════════════════════════════════════════════ */
function loadGuests(){
  var tbody = document.getElementById('guest-tbody');
  if(tbody) tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--fg-3)">⏳ جارٍ تحميل النزلاء...</td></tr>';
  fetch('/api/guests')
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.success){ throw new Error(res.detail||'خطأ'); }
      var raw = res.data || [];
      GUESTS = raw.map(function(g){
        var nm = g.full_name||g.name||'—';
        var parts = nm.trim().split(/\s+/);
        var initials = parts.slice(0,2).map(function(w){ return w[0]||''; }).join('');
        return {
          id:        g.id,
          name:      nm,
          initials:  initials,
          nationality: g.nationality||'—',
          room:      g.room_number||g.room||'—',
          roomType:  g.room_type||'—',
          checkin:   g.check_in||g.checkin||'—',
          checkout:  g.check_out||g.checkout||'—',
          phone:     g.phone||g.mobile||'—',
          balanceLeft: g.balance_due!=null ? String(g.balance_due) : '٠',
          vip:       !!(g.vip||g.is_vip),
          status:    g.status==='departing'||g.checkout_today ? 'departing' : 'ok',
          alerts:    g.alerts||[],
          bookingId: g.booking_id||g.id,
        };
      });
      filterAndRenderGuests();
      updateBadges();
    })
    .catch(function(err){
      var tbody2 = document.getElementById('guest-tbody');
      if(tbody2) tbody2.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:32px;color:var(--danger-600)">⚠ تعذّر تحميل النزلاء — '+err.message+'</td></tr>';
    });
}

/* ═══════════════════════════════════════════════
   API — LOAD ARRIVALS (GET /api/m02/arrivals)
═══════════════════════════════════════════════ */
function loadArrivals(){
  var tbody = document.getElementById('res-tbody');
  if(tbody) tbody.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--fg-3)">⏳ جارٍ تحميل الحجوزات...</td></tr>';
  fetch('/api/m02/arrivals')
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.success){ throw new Error(res.detail||'خطأ'); }
      var raw = res.data || [];
      RESERVATIONS = raw.map(function(b){
        var nm = b.full_name||b.name||'—';
        var parts = nm.trim().split(/\s+/);
        var initials = parts.slice(0,2).map(function(w){ return w[0]||''; }).join('');
        var cin  = (b.check_in||'').split('T')[0];
        var cout = (b.check_out||'').split('T')[0];
        var nights = 0;
        if(cin && cout){ var d1=new Date(cin),d2=new Date(cout); nights=Math.max(0,Math.round((d2-d1)/86400000)); }
        var payMap = {paid:'ok', deposit:'warn', unpaid:'danger', confirmed:'info'};
        var payLbl = {paid:'مدفوع', deposit:'عربون', unpaid:'لم يدفع', confirmed:'مؤكّد'};
        var ps = b.payment_status||b.payment||'confirmed';
        return {
          id:          b.id||b.booking_id||('RES-'+Date.now()),
          name:        nm,
          initials:    initials,
          nationality: b.nationality||'—',
          idNum:       b.id_number||'—',
          idType:      b.id_type||'هوية',
          room:        b.room_number||b.room||'—',
          roomType:    b.room_type||'—',
          checkin:     cin,
          checkout:    cout,
          nights:      nights,
          channel:     b.channel||b.booking_source||'مباشر',
          payment:     payLbl[ps]||ps,
          payClass:    payMap[ps]||'neu',
          amt:         b.total_amount!=null ? String(b.total_amount) : '—',
          vip:         !!(b.vip||b.is_vip),
          phone:       b.phone||b.mobile||'—',
        };
      });
      filterAndRenderRes();
      updateBadges();
    })
    .catch(function(err){
      var tbody2 = document.getElementById('res-tbody');
      if(tbody2) tbody2.innerHTML = '<tr><td colspan="12" style="text-align:center;padding:32px;color:var(--danger-600)">⚠ تعذّر تحميل الحجوزات — '+err.message+'</td></tr>';
    });
}

/* ═══════════════════════════════════════════════
   API — LOAD DEPARTURES (GET /api/m02/departures)
═══════════════════════════════════════════════ */
function loadDepartures(){
  fetch('/api/m02/departures')
    .then(function(r){ return r.json(); })
    .then(function(res){
      if(!res.success){ throw new Error(res.detail||'خطأ'); }
      var raw = res.data || [];
      // Merge today's departures into GUESTS (mark status=departing)
      raw.forEach(function(b){
        var nm = b.full_name||b.name||'—';
        var bid = b.id||b.booking_id;
        var existing = GUESTS.find(function(g){ return g.bookingId===bid||g.id===bid; });
        if(existing){
          existing.status = 'departing';
        } else {
          var parts = nm.trim().split(/\s+/);
          var initials = parts.slice(0,2).map(function(w){ return w[0]||''; }).join('');
          GUESTS.push({
            id:        bid,
            name:      nm,
            initials:  initials,
            nationality: b.nationality||'—',
            room:      b.room_number||b.room||'—',
            roomType:  b.room_type||'—',
            checkin:   (b.check_in||'').split('T')[0],
            checkout:  (b.check_out||'').split('T')[0],
            phone:     b.phone||b.mobile||'—',
            balanceLeft: b.balance_due!=null ? String(b.balance_due) : '٠',
            vip:       !!(b.vip||b.is_vip),
            status:    'departing',
            alerts:    [],
            bookingId: bid,
          });
        }
      });
      filterAndRenderGuests();
      updateBadges();
    })
    .catch(function(err){
      // Non-blocking — departures panel relies on guests already loaded
      console.warn('loadDepartures:', err.message);
    });
}

/* ═══════════════════════════════════════════════
   API — WIRE CHECKIN (POST /api/integration/checkin)
   Cascade: room→occupied, revenue, inventory, KPI
═══════════════════════════════════════════════ */
function cascadeSummary(res){
  var parts = [];
  if(res.room_status || res.room) parts.push('الغرفة: '+(res.room_status||res.room));
  if(res.revenue!=null) parts.push('إيراد: '+(DH.formatSAR ? DH.formatSAR(res.revenue) : res.revenue));
  var inv = res.inventory_deducted||res.inventory;
  if(inv!=null){
    if(typeof inv==='number') parts.push('خصم مخزون: '+inv+' صنف');
    else if(Array.isArray(inv)) parts.push('خصم مخزون: '+inv.length+' صنف');
  }
  return parts.join(' · ');
}
window.doCheckin = function(btn){
  if(btn.disabled) return;
  // Find booking id from row  (id stored in button id="ci-<bookingId>")
  var bid = btn.id.replace('ci-','');
  var r = RESERVATIONS.find(function(x){ return String(x.id)===String(bid); }) || {};
  var amount = parseFloat(r.amt)||0;
  btn.disabled = true;
  btn.textContent = '⏳ جارٍ...';
  DH.fetch('/api/integration/checkin', {
    method:'POST',
    body: JSON.stringify({ booking_id: bid, amount: amount, payment_method:'cash', checkin_by:'استقبال' })
  }).then(function(res){
    if(res){
      btn.textContent = '✓ مسجَّل';
      var sum = cascadeSummary(res);
      toast('تم تسجيل الدخول ✓'+(sum?' — '+sum:''));
    } else {
      btn.disabled = false;
      btn.textContent = 'تسجيل دخول';
      toast('فشل تسجيل الدخول', true);
    }
  });
};

/* ═══════════════════════════════════════════════
   API — WIRE CHECKOUT (POST /api/integration/checkout)
   Cascade: room→cleaning, revenue, KPI
═══════════════════════════════════════════════ */
window.doCheckout = function(gid){
  var g = GUESTS.find(function(x){ return x.id===gid; });
  if(!g) return;
  if(!confirm('تسجيل خروج '+g.name+' من غرفة '+g.room+'؟')) return;
  var bid = g.bookingId||gid;
  DH.fetch('/api/integration/checkout', {
    method:'POST',
    body: JSON.stringify({ booking_id: bid, final_amount: parseFloat(g.balanceLeft)||0, payment_method:'cash' })
  }).then(function(res){
    if(res){
      FLOORS.forEach(function(fl){
        fl.rooms.forEach(function(rm){
          if(rm.num===g.room && rm.status==='occupied'){
            rm.status='cleaning'; rm.guest=null;
          }
        });
      });
      GUESTS = GUESTS.filter(function(x){ return x.id!==gid; });
      filterAndRenderGuests();
      renderFloors();
      updateBadges();
      var sum = cascadeSummary(res);
      toast('تم تسجيل خروج '+g.name+' — غرفة '+g.room+' بانتظار التنظيف ✓'+(sum?' — '+sum:''));
    } else {
      toast('فشل تسجيل الخروج', true);
    }
  });
};

/* ═══════════════════════════════════════════════
   INIT
═══════════════════════════════════════════════ */
loadArrivals();
loadGuests();
loadDepartures();
renderFloors();
renderPermGrid();
renderStaff();
updateBadges();


/* ═══════════════════════════════════════════════
   الجسر إلى الملفات المفصولة

   المنطق كلّه داخل غلافٍ واحد، فالملفات المنقولة لا تراه. تُصدَّر هنا
   الأسماءُ التي تحتاجها صراحةً — ثمانية لا أكثر — بدل فتح الغلاف
   وجعل كل شيء عاماً.

   STAFF تُعرَّض بقارئ وكاتب لأن ملف الموظفين يُعيد إسنادها بعد كل
   تحميل من الخادم؛ نسخةٌ محلية عنده كانت ستتفرّع عن نسخة الغلاف.
═══════════════════════════════════════════════ */
// نداءاتٌ آمنة إلى ما انتقل: تُنفَّذ إن كان الملف الثاني مُحمَّلاً،
// وتصمت إن لم يكن — بدل أن ترمي وتُوقف بقية التهيئة.
function renderPermGrid(){
  if (window.GuestsExtras && window.GuestsExtras.renderPermGrid)
    window.GuestsExtras.renderPermGrid();
}
function renderStaff(){
  if (window.GuestsExtras && window.GuestsExtras.renderStaff)
    window.GuestsExtras.renderStaff();
}
function loadStaffAccountsFromServer(){
  if (window.GuestsExtras && window.GuestsExtras.loadStaffAccountsFromServer)
    return window.GuestsExtras.loadStaffAccountsFromServer();
}

window.GuestsShared = {
  get STAFF(){ return STAFF; },
  set STAFF(v){ STAFF = v; },
  get GUESTS(){ return GUESTS; },
  get RESERVATIONS(){ return RESERVATIONS; },
  get ROLE_PERMS(){ return ROLE_PERMS; },
  get ALL_PROGRAMS(){ return ALL_PROGRAMS; },
  get currentRole(){ return currentRole; },
  toast: toast,
  modal: modal,
  updateBadges: updateBadges
};

})();
