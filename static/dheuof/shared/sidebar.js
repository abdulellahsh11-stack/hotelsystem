/* =========================================================================
   Static sidebar builder — shared by all stub experiences.
   No React, no Babel. Just call StaticSidebar.render(activeId).
   ========================================================================= */
(function () {
  // إعداد المنشأة أوّلاً لا برقمٍ في تسلسل البرامج: هو ما يُبدأ به،
  // ومنه تُسجَّل الغرف — وبلا غرف لا تعمل بقية الوحدات أصلاً.
  var SETUP = { id: "00-setup", ar: "إعداد المنشأة", num: "00" };

  var MODULES = [
    { id: "01-guests",            ar: "الضيوف",            num: "01" },
    { id: "02-shumus",            ar: "شموس",             num: "02" },
    { id: "03-tourism",           ar: "المستندات الحكومية", num: "03" },
    { id: "04-inventory",         ar: "المخزون والضيافة", num: "04" },
    { id: "05-warehouse",         ar: "مستودع الصيانة",  num: "05" },
    { id: "06-accounting",        ar: "المحاسبة",         num: "06" },
    { id: "07-pos",               ar: "نقاط البيع",       num: "07" },
    { id: "08-smart-key",         ar: "المفتاح الذكي",     num: "08" },
    { id: "09-hr",                ar: "الموارد البشرية",   num: "09" },
    { id: "10-channel-marketing", ar: "تسويق القنوات",    num: "10" },
    { id: "11-kpis",              ar: "مؤشرات الأداء",     num: "11" },
    { id: "12-analytics",         ar: "تحليل البيانات",    num: "12" },
    { id: "13-staff-tracker",     ar: "أداء الموظفين",    num: "13" },
    { id: "14-manager-goals",     ar: "أهداف المدير",     num: "14" },
    { id: "15-tourism-trips",     ar: "جولات سياحية",     num: "15" },
    { id: "16-staff-app",         ar: "تطبيق الموظفين",   num: "16" },
    { id: "17-bookings",          ar: "حجوزات القنوات",   num: "17" },
    { id: "18-listing",           ar: "العرض والحجز",     num: "18" },
  ];

  /* ── HTML-escape (prevents stored XSS from user-supplied session fields) ── */
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ── Auth helpers ──────────────────────────────────────────────────────── */
  // الجلسة الحقيقية في كوكي HttpOnly لا يراها الجافاسكربت إطلاقاً، فقراءة
  // `localStorage` وحدها كانت تُعلن «زائر» لمالكٍ داخلٍ فعلاً — في كل صفحة،
  // مع زرّ «سجّل / دخول» يوحي أن الدخول فشل وهو ناجح. الخادم هو المرجع،
  // و`localStorage` مجرّد ذاكرةٍ مؤقّتة تُغني عن وميضٍ قبل وصول الردّ.
  function getSession() {
    if (SERVER_SESSION) return SERVER_SESSION;
    try { return JSON.parse(localStorage.getItem('dheuof_session') || 'null'); } catch(e) { return null; }
  }

  var SERVER_SESSION = null;

  /* يسأل الخادم من أنا، ثم يُعيد رسم الشريط بالحقيقة. */
  function refreshFromServer(opts) {
    fetch('/api/staff/me', { credentials: 'same-origin' })
      .then(function(r){ return r.ok ? r.json() : null; })
      .then(function(body){
        var me = body && body.data;
        if (!me || !me.client_id) return;          // زائرٌ فعلاً
        SERVER_SESSION = {
          name: me.full_name || me.username || 'مالك المنشأة',
          email: me.username || '',
          property: me.property_name || '',
          role: me.role,
          plan: 'active',
          // الخادم أكّد الجلسة الآن: نختمها بطابعٍ زمني. بدونه يراها
          // `isSessionExpired` منتهيةً (لا ts رقمي) فيطرد مستخدماً داخلاً
          // فعلاً إلى `/` عند أوّل نبضة مؤقّت (٦٠ث) — كان يخرج من «تسجيل
          // نزيل جديد» خلال ثوانٍ. الخادم يبقى المرجع الحقيقي للانتهاء.
          ts: Date.now()
        };
        try { localStorage.setItem('dheuof_session', JSON.stringify(SERVER_SESSION)); } catch(e) {}
        var sb = document.querySelector('.dh-sidebar');
        var tb = document.querySelector('.dh-topbar');
        if (sb) sb.outerHTML = renderSidebar((opts||{}).activeId, opts||{});
        if (tb) tb.outerHTML = renderTopBar(opts||{});
      })
      .catch(function(){ /* الشبكة ساقطة: يبقى الرسم الأول */ });
  }
  function saveSession(s) {
    // NOTE: session token lives in an HttpOnly+Secure+SameSite=Lax cookie set by the server.
    // localStorage here holds only non-sensitive UI state (name, plan).
    // Do NOT store passwords or raw tokens here.
    var safe = { email: s.email, name: s.name, plan: s.plan, ts: s.ts, twofa: s.twofa };
    localStorage.setItem('dheuof_session', JSON.stringify(safe));
  }
  function clearSession() {
    localStorage.removeItem('dheuof_session');
  }

  /* ── Toast helper ──────────────────────────────────────────────────────── */
  function showToast(msg, type) {
    var t = document.createElement('div');
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:' +
      (type === 'err' ? '#C0392B' : '#1B4D3D') +
      ';color:#fff;padding:12px 24px;border-radius:10px;font-family:"Tajawal","Segoe UI",sans-serif;font-size:14px;z-index:999999;box-shadow:0 4px 20px rgba(0,0,0,.3);direction:rtl;transition:opacity .3s';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function(){ t.style.opacity = '0'; setTimeout(function(){ if(t.parentNode) t.remove(); }, 320); }, 2600);
  }

  /* ── Auth overlay (blocks page until logged in) ────────────────────────── */


  /* ── Update topbar with real session info ──────────────────────────────── */
  function updateTopbarUser(session) {
    var av = document.querySelector('.dh-user .av');
    var nameEl = document.querySelector('.dh-user .nm .ar');
    var roleEl = document.querySelector('.dh-user .nm .role');
    if (!session) return;
    var initials = session.name ? session.name.split(' ').map(function(w){ return w[0]; }).join('').slice(0,2) : 'م';
    if (av) av.textContent = initials;
    if (nameEl) nameEl.textContent = session.name || session.email;
    if (roleEl) roleEl.textContent = session.property ? session.property : (session.plan === 'trial' ? 'تجربة مجانية' : 'مشترك');
  }

  /* ── Sidebar renderer ─────────────────────────────────────────────────── */
  function renderSidebar(activeId, opts) {
    opts = opts || {};
    var property = opts.property || { ar: "فندق الواحة الذهبية", en: "Golden Oasis · Riyadh" };
    var home = opts.homeHref || "../index.html";
    var session = getSession();
    if (session && session.property) {
      property = { ar: session.property, en: session.email || '' };
    }

    return '<aside class="dh-sidebar">' +
      '<a class="dh-brand" href="' + home + '" style="text-decoration:none; cursor:pointer">' +
        '<img class="dh-mark" src="/static/dheuof/assets/logo-mark.svg" alt="ضيوف"/>' +
        '<div class="dh-brand-name"><div class="ar">ضيوف</div><div class="en">Dheuof</div></div>' +
      '</a>' +
      '<nav class="dh-nav"><div class="dh-nav-group">' +
        '<div class="dh-nav-label">الإعداد</div>' +
        [SETUP].map(function(m){
          var href = '../' + m.id + '/index.html';
          return '<a class="dh-nav-item' + (m.id === activeId ? ' is-active' : '') + '" href="' + href + '" style="text-decoration:none">' +
            '<span class="ic" style="font-family:var(--font-mono);font-size:10px;width:18px;text-align:center;opacity:0.65;font-weight:500">' + m.num + '</span>' +
            '<span class="lbl">' + m.ar + '</span></a>';
        }).join('') +
        '<div class="dh-nav-label" style="margin-top:14px">١٨ برنامجاً</div>' +
        MODULES.map(function(m) {
          var isActive = m.id === activeId;
          var href = '../' + m.id + '/index.html';
          return '<a class="dh-nav-item' + (isActive ? ' is-active' : '') + '" href="' + href + '" style="text-decoration:none">' +
            '<span class="ic" style="font-family:var(--font-mono);font-size:10px;width:18px;text-align:center;opacity:0.65;font-weight:500">' + m.num + '</span>' +
            '<span class="lbl">' + m.ar + '</span>' +
          '</a>';
        }).join('') +
      '</div></nav>' +
      (!session ? (
        '<div class="dh-trial-cta">' +
          '<div class="dh-trial-badge">تجربة مجانية · 30 يوم</div>' +
          '<div class="dh-trial-desc">جميع الميزات متاحة بدون بطاقة ائتمان</div>' +
          '<button onclick="dhShowAuth()" class="dh-trial-btn-reg" style="border:none;cursor:pointer;width:100%;text-align:center">سجّل مجاناً الآن</button>' +
          '<a href="/static/dheuof/packages.html" class="dh-trial-pkg-link">عرض الباقات والأسعار</a>' +
        '</div>'
      ) : (
        '<div class="dh-trial-cta" style="background:rgba(201,168,95,.08);border-color:rgba(201,168,95,.2)">' +
          '<div class="dh-trial-badge" style="background:rgba(201,168,95,.2);color:var(--gold-300)">✓ مشترك نشط</div>' +
          '<div class="dh-trial-desc">' + esc(session.name || session.email) + '</div>' +
          '<button onclick="dhLogout()" class="dh-trial-btn-reg" style="border:none;cursor:pointer;width:100%;text-align:center;background:rgba(255,255,255,.1);color:var(--gold-200)">تسجيل الخروج</button>' +
        '</div>'
      )) +
      '<div class="dh-side-foot">' +
        // لوحة التحكم لم يكن يشير إليها رابطٌ واحد من أي وحدة، ومنها
        // تُسجَّل الغرف والأدوار — فيصطدم المستخدم برسالة «سجّل غرفك من
        // لوحة التحكم» ولا يجد إليها سبيلاً. وهنا يُرسم دائماً: وضعُه في
        // فرع «مشترك نشط» يجعله يتبع `localStorage` وهو فارغ لمن يدخل
        // من صفحة الدخول الحقيقية.
        '<a href="/static/dashboard.html" class="dh-dashboard-link" style="display:block;text-decoration:none;text-align:center;padding:9px 12px;margin-bottom:10px;border-radius:8px;background:rgba(255,255,255,.12);color:var(--gold-200);font-size:12.5px;font-weight:600">⚙️ لوحة التحكم</a>' +
        '<div class="dh-property">' +
          '<div class="ar">' + esc(property.ar) + '</div>' +
          '<div class="en">' + esc(property.en || '') + '</div>' +
        '</div>' +
      '</div>' +
    '</aside>';
  }

  /* ── Topbar renderer ──────────────────────────────────────────────────── */
  function renderTopBar(opts) {
    opts = opts || {};
    var placeholder = opts.placeholder || "بحث...";
    var session = getSession();
    var userName = session ? (session.name || session.email) : 'زائر';
    var userRole = session ? (session.property || (session.plan === 'trial' ? 'تجربة مجانية' : 'مشترك')) : '';
    var initials = session && session.name ? session.name.split(' ').map(function(w){ return w[0]; }).join('').slice(0,2) : 'زر';

    return '<header class="dh-topbar">' +
      '<button class="dh-topbar-menu-btn" aria-label="القائمة" onclick="(function(){var s=document.querySelector(\'.dh-sidebar\');if(s)s.classList.toggle(\'is-open\');})()">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>' +
      '</button>' +
      '<div class="dh-search">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>' +
        '<input placeholder="' + placeholder + '"/>' +
        '<span class="kbd">⌘K</span>' +
      '</div>' +
      '<div class="dh-top-actions">' +
        (!session ?
          '<button onclick="dhShowAuth()" class="dh-trial-topbtn" style="border:none;cursor:pointer">' +
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:13px;height:13px"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>' +
            'سجّل / دخول' +
          '</button>'
          :
          '<button onclick="dhShowAuth()" class="dh-trial-topbtn" style="border:none;cursor:pointer;background:linear-gradient(135deg,#1B4D3D,#0E2A22)">' +
            '✓ مشترك' +
          '</button>'
        ) +
        '<div class="dh-user">' +
          '<div class="av">' + esc(initials) + '</div>' +
          '<div class="nm"><div class="ar">' + esc(userName) + '</div><div class="role">' + esc(userRole) + '</div></div>' +
        '</div>' +
      '</div>' +
    '</header>';
  }

  /* ── Trial banner (only when NOT logged in) ───────────────────────────── */
  function injectTrialBanner() {
    var session = getSession();
    if (session) return; // logged-in users don't see the floating banner
    var dismissed = localStorage.getItem('dheuof_trial_banner_dismissed');
    if (dismissed) return;
    var b = document.createElement('div');
    b.id = 'dh-float-trial';
    b.innerHTML =
      '<div class="dh-ftrial-inner">' +
        '<span class="dh-ftrial-spark">✦</span>' +
        '<div class="dh-ftrial-text">' +
          '<strong>جرّب ضيوف مجاناً لمدة 30 يوماً</strong>' +
          '<span>١٧ برنامج · جميع الميزات · بدون بطاقة ائتمان</span>' +
        '</div>' +
        '<div class="dh-ftrial-actions">' +
          '<button onclick="dhShowAuth()" class="dh-ftrial-cta" style="border:none;cursor:pointer">سجّل مجاناً</button>' +
          '<a href="/static/dheuof/packages.html" class="dh-ftrial-pkg">عرض الباقات</a>' +
        '</div>' +
        '<button class="dh-ftrial-close" onclick="(function(){localStorage.setItem(\'dheuof_trial_banner_dismissed\',\'1\');var el=document.getElementById(\'dh-float-trial\');if(el)el.remove();})()" aria-label="إغلاق">✕</button>' +
      '</div>';
    document.body.appendChild(b);
    setTimeout(function(){ b.classList.add('dh-ftrial-in'); }, 100);
  }

  /* ── Session timeout (default 8h, configurable from security page) ────── */
  var SESSION_TIMEOUT_MS = 8 * 3600 * 1000; // 8 hours default

  function getTimeoutMs() {
    var v = parseInt(localStorage.getItem('dheuof_session_timeout'), 10);
    return (isFinite(v) && v > 0) ? v : SESSION_TIMEOUT_MS;
  }

  // A session is expired if it has no numeric ts, or it is older than the limit.
  function isSessionExpired(session) {
    if (!session) return false;
    var ts = Number(session.ts);
    if (!isFinite(ts)) return true; // missing/corrupt ts -> force re-auth
    return (Date.now() - ts) > getTimeoutMs();
  }

  function checkSessionTimeout(opts) {
    var session = getSession();
    if (!session) return;
    if (isSessionExpired(session)) {
      clearSession();
      /* Re-render as guest and show auth wall */
      var sb = document.querySelector('.dh-sidebar');
      var tb = document.querySelector('.dh-topbar');
      if (sb) sb.outerHTML = renderSidebar(opts ? opts.activeId : undefined, opts);
      if (tb) tb.outerHTML = renderTopBar(opts);
      window.location.href = '/';
    }
  }

  /* ── Mount — checks auth FIRST, blocks page if not logged in ─────────── */
  function mount(opts) {
    opts = opts || {};

    // Expose global helpers before anything renders
    // الدخول والتسجيل يقعان في الصفحة الرئيسية، لا في جدارٍ منبثق.
    //
    // كان هنا جدارٌ يغطّي الصفحة بـ`z-index:99999` ويقرّر ظهوره من
    // `localStorage` — لا من جلسة الخادم. فمن يدخل من صفحة الدخول
    // الحقيقية تُضبط جلسته في كوكي HttpOnly ويبقى `localStorage` فارغاً،
    // فينزل الجدار **فوق مستخدمٍ مسجَّل الدخول فعلاً** ويعترض كل نقرة:
    // لا حفظ، ولا تخصيص، ولا فاتورة. والبيانات تُقرأ من الخادم بنجاح
    // خلفه — فتبدو المنصة كأنها لا تستجيب وهي تعمل.
    window.dhShowAuth = function() {
      window.location.href = '/';
    };

    window.dhLogout = function() {
      if (!confirm('تسجيل الخروج من النظام؟')) return;
      clearSession();
      // Show auth wall again
      window.dhShowAuth();
      // Re-render sidebar + topbar as guest
      var sb = document.querySelector('.dh-sidebar');
      var tb = document.querySelector('.dh-topbar');
      if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
      if (tb) tb.outerHTML = renderTopBar(opts);
    };

    var session = getSession();

    /* Check for session timeout before rendering */
    if (session && isSessionExpired(session)) {
      clearSession();
      session = null;
    }

    // الصفحة تُرسم دائماً. حجبُ صفحات البرنامج مسؤولية الخادم وحده —
    // فهو يعرف الجلسة الحقيقية، والمتصفّح لا يعرف إلا ما كُتب له محلياً.
    var sb = document.getElementById("sidebar-slot");
    var tb = document.getElementById("topbar-slot");
    if (sb) sb.outerHTML = renderSidebar(opts.activeId, opts);
    if (tb) tb.outerHTML = renderTopBar(opts);

    refreshFromServer(opts);

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', injectTrialBanner);
    } else {
      injectTrialBanner();
    }

    /* Periodically expire the session while the page stays open (every 60s) */
    if (!window.__dhTimeoutTimer) {
      window.__dhTimeoutTimer = setInterval(function(){ checkSessionTimeout(opts); }, 60 * 1000);
    }
  }

  window.StaticSidebar = { renderSidebar, renderTopBar, mount, MODULES, getSession, clearSession };
})();
