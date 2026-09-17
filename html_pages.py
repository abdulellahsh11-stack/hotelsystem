#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
html_pages.py — دوال توليد صفحات HTML
لوحات التحكم وصفحات المصادقة (Admin + Client)
"""
_NAV = """
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:'Segoe UI',Tahoma,Arial,sans-serif}
body{direction:rtl;background:#F8FAFC;color:#1e293b;min-height:100vh}
.sidebar{position:fixed;top:0;right:0;width:240px;height:100vh;background:#0F2640;padding:20px 0;overflow-y:auto;z-index:100}
.sidebar .logo{padding:0 20px 20px;border-bottom:1px solid rgba(255,255,255,.1);margin-bottom:10px}
.sidebar .logo h1{color:#fff;font-size:22px;font-weight:700}
.sidebar .logo small{color:#94a3b8;font-size:12px}
.sidebar a{display:flex;align-items:center;gap:10px;padding:12px 20px;color:#94a3b8;text-decoration:none;transition:.2s;font-size:14px;border-right:3px solid transparent}
.sidebar a:hover,.sidebar a.active{color:#fff;background:rgba(255,255,255,.07);border-right-color:#185FA5}
.sidebar a span.icon{font-size:18px}
.main{margin-right:240px;padding:24px;min-height:100vh}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}
.topbar h2{font-size:22px;font-weight:700;color:#0F2640}
.btn{display:inline-flex;align-items:center;gap:6px;padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-size:14px;font-weight:600;transition:.2s;text-decoration:none}
.btn-primary{background:#185FA5;color:#fff}.btn-primary:hover{background:#1a4f87}
.btn-success{background:#10B981;color:#fff}.btn-success:hover{background:#059669}
.btn-danger{background:#ef4444;color:#fff}.btn-danger:hover{background:#dc2626}
.btn-outline{background:transparent;color:#185FA5;border:2px solid #185FA5}.btn-outline:hover{background:#185FA5;color:#fff}
.card{background:#fff;border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,.08);padding:24px;margin-bottom:20px}
.card-title{font-size:16px;font-weight:700;color:#0F2640;margin-bottom:16px;padding-bottom:12px;border-bottom:2px solid #f1f5f9}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 3px rgba(0,0,0,.08);border-top:4px solid #185FA5}
.stat-card.green{border-top-color:#10B981}.stat-card.gold{border-top-color:#F59E0B}.stat-card.red{border-top-color:#ef4444}
.stat-card .value{font-size:28px;font-weight:800;color:#0F2640;margin:8px 0}
.stat-card .label{font-size:13px;color:#64748b;font-weight:500}
table{width:100%;border-collapse:collapse;font-size:14px}
th{background:#f8fafc;padding:12px 16px;text-align:right;font-weight:600;color:#475569;border-bottom:2px solid #e2e8f0}
td{padding:12px 16px;border-bottom:1px solid #f1f5f9;color:#334155}
tr:hover td{background:#f8fafc}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:12px;font-weight:600}
.badge-green{background:#dcfce7;color:#166534}.badge-blue{background:#dbeafe;color:#1d4ed8}
.badge-yellow{background:#fef9c3;color:#854d0e}.badge-red{background:#fee2e2;color:#991b1b}
.form-group{margin-bottom:16px}
.form-group label{display:block;font-size:13px;font-weight:600;color:#475569;margin-bottom:6px}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:10px 14px;border:2px solid #e2e8f0;border-radius:8px;font-size:14px;color:#334155;outline:none;transition:.2s}
.form-group input:focus,.form-group select:focus{border-color:#185FA5}
.alert{padding:12px 16px;border-radius:8px;margin-bottom:16px;font-size:14px}
.alert-error{background:#fee2e2;color:#991b1b;border:1px solid #fecaca}
.alert-success{background:#dcfce7;color:#166534;border:1px solid #bbf7d0}
@media(max-width:768px){.sidebar{width:100%;height:auto;position:relative}.main{margin-right:0}}
</style>
"""


_SEO_BASE = """<meta name="description" content="ضيوف — منصة إدارة الفنادق والشقق المخدومة الذكية في السعودية. حجوزات، نزلاء، فواتير، تقارير، واتساب.">
<meta name="keywords" content="نظام فنادق, إدارة فندق, شقق مخدومة, حجوزات, نزلاء, فواتير ضريبية, واتساب فندق, ضيوف, dheuof">
<meta name="robots" content="index, follow">
<meta property="og:title" content="ضيوف — منصة الضيافة الذكية">
<meta property="og:description" content="إدارة فندقك بذكاء — حجوزات، نزلاء، فواتير، تقارير متقدمة وأكثر من 17 وحدة.">
<meta property="og:type" content="website">
<meta property="og:locale" content="ar_SA">
<link rel="canonical" href="https://dheuof.com/">"""


def _login_page(error: str = "", ref_code: str = "") -> str:
    err_html = f'<div class="alert alert-error">{error}</div>' if error else ""
    ref_field = f'<input type="hidden" id="ref-code" value="{ref_code}">' if ref_code else '<input type="hidden" id="ref-code" value="">'
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ضيوف — نظام إدارة الفنادق والشقق المخدومة</title>
{_SEO_BASE}
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:Arial,Helvetica,sans-serif;background:linear-gradient(135deg,#1B4D3D,#0E2A22);min-height:100vh;display:flex;align-items:center;justify-content:center;padding:20px}}
  .card{{background:#fff;border-radius:18px;padding:44px 40px;width:100%;max-width:440px;box-shadow:0 24px 64px rgba(0,0,0,0.35)}}
  .logo{{text-align:center;margin-bottom:30px}}
  .logo h1{{color:#1B4D3D;font-size:2rem;font-weight:700}}
  .logo p{{color:#64748b;font-size:0.9rem;margin-top:4px}}
  .tabs{{display:flex;border-bottom:2px solid #e2e8f0;margin-bottom:28px}}
  .tab{{flex:1;padding:10px;text-align:center;cursor:pointer;color:#64748b;font-weight:500;transition:.2s}}
  .tab.active{{color:#1B4D3D;border-bottom:2px solid #1B4D3D;margin-bottom:-2px}}
  .form-group{{margin-bottom:20px}}
  label{{display:block;color:#374151;font-size:.875rem;font-weight:500;margin-bottom:6px}}
  input,select{{width:100%;padding:11px 14px;border:1.5px solid #d1d5db;border-radius:8px;font-size:.95rem;transition:.2s;font-family:inherit;color:#1e293b}}
  input:focus,select:focus{{outline:none;border-color:#1B4D3D;box-shadow:0 0 0 3px rgba(27,77,61,0.1)}}
  .btn{{width:100%;padding:13px;background:linear-gradient(135deg,#1B4D3D,#0E2A22);color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;transition:.2s;font-family:inherit}}
  .btn:hover{{filter:brightness(1.08)}}
  .alert-error{{background:#fef2f2;color:#dc2626;padding:10px 14px;border-radius:8px;font-size:.875rem;margin-bottom:16px}}
  .pane{{display:none}} .pane.active{{display:block}}
  .footer{{text-align:center;margin-top:12px;color:#9ca3af;font-size:.8rem}}
  .contact-box{{display:flex;flex-direction:column;gap:8px;align-items:center;margin-top:24px;padding-top:20px;border-top:1px solid #e2e8f0}}
  .contact-box a{{color:#1B4D3D;text-decoration:none;font-size:.88rem;font-weight:500}}
  .contact-box a:hover{{text-decoration:underline}}
  .switch-link{{text-align:center;margin-top:16px;font-size:.85rem;color:#64748b}}
  .switch-link a{{color:#1B4D3D;text-decoration:none}}
  .staff-link{{text-align:center;margin-top:20px;padding-top:18px;border-top:1px solid #eee;font-size:12.5px;color:#888}}
  .staff-link a{{color:#1B4D3D;font-weight:600;text-decoration:none}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>&#127960; ضيوف</h1>
    <p>نظام إدارة الفنادق والشقق المخدومة</p>
  </div>
  <div class="tabs">
    <div class="tab active" onclick="showTab('login')">تسجيل الدخول</div>
    <div class="tab" onclick="showTab('register')">تسجيل جديد</div>
  </div>

  <div id="err-msg" style="display:none" class="alert-error"></div>
  {err_html}

  <div id="pane-login" class="pane active">
    <div class="form-group">
      <label>معرّف المنشأة</label>
      <input type="text" id="login-id" placeholder="hotel-001" autocomplete="username">
    </div>
    <div class="form-group">
      <label>كلمة المرور</label>
      <input type="password" id="login-pass" placeholder="••••••••" autocomplete="current-password" onkeydown="if(event.key==='Enter')doLogin()">
    </div>
    <button class="btn" onclick="doLogin()">دخول</button>
  </div>

  <div id="pane-register" class="pane">
    {ref_field}
    <div class="form-group">
      <label>اسم المنشأة</label>
      <input type="text" id="reg-name" placeholder="فندق الواحة">
    </div>
    <div class="form-group">
      <label>اسم المالك / المسؤول</label>
      <input type="text" id="reg-owner" placeholder="محمد الأحمد">
    </div>
    <div class="form-group">
      <label>رقم الجوال</label>
      <input type="tel" id="reg-phone" dir="ltr" inputmode="numeric" placeholder="05XXXXXXXX">
    </div>
    <div class="form-group">
      <label>المدينة</label>
      <input type="text" id="reg-city" placeholder="الرياض">
    </div>
    <div class="form-group">
      <label>السجل التجاري <span style="color:#9ca3af;font-weight:400">(اختياري)</span></label>
      <input type="text" id="reg-cr" dir="ltr" inputmode="numeric" placeholder="1010XXXXXX">
    </div>
    <div class="form-group">
      <label>البريد الإلكتروني <span style="color:#ef4444;font-size:.8rem">* سيصلك معرّفك عليه</span></label>
      <input type="email" id="reg-email" dir="ltr" placeholder="your@email.com" required>
    </div>
    <div class="form-group">
      <label>كلمة المرور</label>
      <input type="password" id="reg-pass" placeholder="••••••••">
    </div>
    <div class="form-group">
      <label>مفتاح التفعيل <span style="color:#9ca3af;font-weight:400">(اختياري)</span></label>
      <input type="text" id="reg-key" placeholder="XXXX-XXXX-XXXX-XXXX">
    </div>
    <button class="btn" onclick="doRegister()">تسجيل وبدء التجربة المجانية</button>
  </div>

  <div class="contact-box">
    <a href="mailto:info@dheuof.com">&#9993; info@dheuof.com</a>
    <a href="https://wa.me/966565009696" target="_blank" rel="noopener">&#128241; واتساب: +966 56 500 9696</a>
  </div>
  <p class="staff-link">موظف في منشأة مشتركة؟ <a href="/static/dheuof/staff-login.html">دخول الموظفين ←</a></p>
  <div class="footer">dheuof.com &copy; 2026 — منصة ضيوف للضيافة الذكية</div>
</div>
<script>
function showTab(t){{
  document.querySelectorAll('.tab').forEach((el,i)=>el.classList.toggle('active',i===(t==='login'?0:1)));
  document.querySelectorAll('.pane').forEach(el=>el.classList.remove('active'));
  document.getElementById('pane-'+t).classList.add('active');
  document.getElementById('err-msg').style.display='none';
}}
function showErr(msg){{var e=document.getElementById('err-msg');e.textContent=msg;e.style.display='block';}}
async function doLogin(){{
  const client_id=document.getElementById('login-id').value.trim();
  const password=document.getElementById('login-pass').value;
  if(!client_id||!password)return showErr('يرجى ملء جميع الحقول');
  const r=await fetch('/api/login',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:'client_id='+encodeURIComponent(client_id)+'&password='+encodeURIComponent(password)}});
  if(r.redirected||r.ok){{location.href='/';return;}}
  const t=await r.text();
  showErr('بيانات الدخول غير صحيحة');
}}
async function doRegister(){{
  const name=document.getElementById('reg-name').value.trim();
  const owner=document.getElementById('reg-owner').value.trim();
  const phone=document.getElementById('reg-phone').value.trim();
  const city=document.getElementById('reg-city').value.trim();
  const cr=document.getElementById('reg-cr').value.trim();
  const email=document.getElementById('reg-email').value.trim();
  const pass=document.getElementById('reg-pass').value;
  const key=document.getElementById('reg-key').value.trim();
  const ref=document.getElementById('ref-code')?.value||'';
  if(!name||!pass)return showErr('اسم المنشأة وكلمة المرور مطلوبان');
  if(!email)return showErr('البريد الإلكتروني مطلوب — سيصلك معرّفك الرقمي عليه');
  if(pass.length<6)return showErr('كلمة المرور ٦ أحرف على الأقل');
  const r=await fetch('/api/client/register',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hotel_name:name,name:owner||name,password:pass,phone:phone,city:city,cr_number:cr,email:email,activation_key:key,ref_code:ref}})}});
  const d=await r.json();
  if(d.ok||d.success){{
    const cid=d.client_id||'';
    alert('✅ تم التسجيل بنجاح!\\n\\nمعرّفك الرقمي:\\n'+cid+'\\n\\nتم إرساله إلى بريدك الإلكتروني — احتفظ به للدخول لاحقاً.');
    location.href='/';
  }}else showErr(d.error||'خطأ في التسجيل');
}}
</script>
</body>
</html>"""


def _admin_login_page(error: str = "") -> str:
    err_html = f'<div class="alert-error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ضيوف — لوحة الإدارة</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#0F2640;min-height:100vh;display:flex;align-items:center;justify-content:center}}
  .card{{background:#fff;border-radius:16px;padding:48px 40px;width:100%;max-width:380px;box-shadow:0 20px 60px rgba(0,0,0,0.4)}}
  .logo{{text-align:center;margin-bottom:32px}}
  .logo h1{{color:#0F2640;font-size:1.8rem;font-weight:700}}
  .logo span{{display:inline-block;background:#0F2640;color:#F59E0B;padding:4px 12px;border-radius:20px;font-size:.75rem;margin-top:6px}}
  .form-group{{margin-bottom:20px}}
  label{{display:block;color:#374151;font-size:.875rem;font-weight:500;margin-bottom:6px}}
  input{{width:100%;padding:11px 14px;border:1.5px solid #d1d5db;border-radius:8px;font-size:.95rem;transition:.2s;font-family:inherit}}
  input:focus{{outline:none;border-color:#0F2640}}
  .btn{{width:100%;padding:13px;background:#0F2640;color:#fff;border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;font-family:inherit}}
  .btn:hover{{background:#185FA5}}
  .alert-error{{background:#fef2f2;color:#dc2626;padding:10px 14px;border-radius:8px;font-size:.875rem;margin-bottom:16px}}
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <h1>&#127960; ضيوف</h1>
    <span>لوحة التحكم الرئيسية</span>
  </div>
  {err_html}
  <div class="form-group">
    <label>كلمة المرور</label>
    <input type="password" id="pass" placeholder="••••••••" onkeydown="if(event.key==='Enter')doLogin()">
  </div>
  <button class="btn" onclick="doLogin()">دخول</button>
</div>
<script>
async function doLogin(){{
  const password=document.getElementById('pass').value;
  if(!password)return;
  const r=await fetch('/api/admin/login',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body:'password='+encodeURIComponent(password)}});
  if(r.ok||r.redirected){{location.href='/admin';return;}}
  document.querySelector('.card').insertAdjacentHTML('afterbegin','<div class="alert-error">كلمة المرور غير صحيحة</div>');
}}
</script>
</body>
</html>"""


def _admin_dashboard(clients: list, stats: dict) -> str:
    return """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ضيوف — لوحة الإدارة</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#f0f4f8;color:#1e293b;display:flex;min-height:100vh;direction:rtl}
.sidebar{width:220px;background:#0F2640;min-height:100vh;display:flex;flex-direction:column;position:fixed;right:0;top:0;bottom:0;z-index:100}
.sidebar .logo{padding:24px 20px;border-bottom:1px solid rgba(255,255,255,.1)}
.sidebar .logo h1{color:#fff;font-size:1.4rem;font-weight:700}
.sidebar .logo small{color:#94a3b8;font-size:.75rem}
.sidebar a{display:flex;align-items:center;gap:10px;padding:12px 20px;color:#cbd5e1;text-decoration:none;font-size:.875rem;transition:.2s}
.sidebar a:hover,.sidebar a.active{background:rgba(255,255,255,.1);color:#fff}
.sidebar a .icon{font-size:1rem}
.sidebar .spacer{flex:1}
.main{margin-right:220px;flex:1;padding:0;min-height:100vh}
.topbar{background:#fff;padding:16px 28px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 1px 4px rgba(0,0,0,.08);position:sticky;top:0;z-index:50}
.topbar h2{font-size:1rem;font-weight:600;color:#0F2640}
.content{padding:24px 28px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:24px}
.stat{background:#fff;border-radius:12px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.06);border-top:3px solid #185FA5}
.stat.g{border-top-color:#10B981}.stat.y{border-top-color:#F59E0B}.stat.r{border-top-color:#ef4444}.stat.p{border-top-color:#8b5cf6}
.stat .val{font-size:1.8rem;font-weight:700;color:#0F2640}.stat .lbl{font-size:.75rem;color:#64748b;margin-top:4px}
.card{background:#fff;border-radius:12px;padding:20px 24px;box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:20px}
.card-hdr{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #f1f5f9}
.card-hdr h3{font-size:.9rem;font-weight:600;color:#0F2640}
table{width:100%;border-collapse:collapse;font-size:.825rem}
th{background:#f8fafc;padding:10px 12px;text-align:right;font-weight:600;color:#64748b;border-bottom:2px solid #e2e8f0}
td{padding:10px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:hover td{background:#fafbfc}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:.75rem;font-weight:600}
.bg{background:#dcfce7;color:#16a34a}.by{background:#fef9c3;color:#ca8a04}.br{background:#fee2e2;color:#dc2626}.bb{background:#dbeafe;color:#1d4ed8}.bp{background:#ede9fe;color:#7c3aed}
.btn{border:none;padding:7px 14px;border-radius:8px;cursor:pointer;font-size:.8rem;font-weight:600;transition:.2s}
.btn-p{background:#185FA5;color:#fff}.btn-p:hover{background:#0F4A8A}
.btn-g{background:#10B981;color:#fff}.btn-g:hover{background:#059669}
.btn-r{background:#ef4444;color:#fff}.btn-r:hover{background:#dc2626}
.btn-s{background:#f1f5f9;color:#374151}.btn-s:hover{background:#e2e8f0}
.btn-y{background:#F59E0B;color:#fff}.btn-y:hover{background:#D97706}
.pane{display:none}.pane.active{display:block}
.alert-exp{background:#fef3c7;border:1px solid #fbbf24;border-radius:8px;padding:10px 14px;font-size:.8rem;color:#92400e;margin-bottom:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-left:6px}
.dot-g{background:#10B981}.dot-y{background:#F59E0B}.dot-r{background:#ef4444}
.modal-bg{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;align-items:center;justify-content:center}
.modal-bg.open{display:flex}
.modal{background:#fff;border-radius:16px;padding:28px;width:100%;max-width:520px;max-height:90vh;overflow-y:auto}
.modal h4{font-size:1rem;font-weight:700;color:#0F2640;margin-bottom:20px}
.fg{margin-bottom:14px}
.fg label{display:block;font-size:.8rem;font-weight:600;color:#374151;margin-bottom:5px}
.fg input,.fg select{width:100%;padding:8px 12px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.875rem;outline:none}
.fg input:focus,.fg select:focus{border-color:#185FA5}
.fg-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.tag{display:inline-block;background:#e0f2fe;color:#0369a1;padding:2px 8px;border-radius:4px;font-size:.7rem;font-weight:600;margin-left:4px}
</style>
</head>
<body>
<div class="sidebar">
  <div class="logo"><h1>ضيوف</h1><small>لوحة الإدارة</small></div>
  <a href="#" class="active" onclick="nav('overview',this)"><span class="icon">&#128200;</span> الرئيسية</a>
  <a href="#" onclick="nav('clients',this)"><span class="icon">&#127970;</span> المنشآت</a>
  <a href="#" onclick="nav('sessions',this)"><span class="icon">&#128101;</span> الجلسات النشطة</a>
  <a href="#" onclick="nav('subs',this)"><span class="icon">&#128203;</span> الاشتراكات</a>
  <a href="#" onclick="nav('packages',this)"><span class="icon">&#128176;</span> أسعار الباقات</a>
  <a href="#" onclick="nav('employees',this)"><span class="icon">&#128188;</span> الموظفون</a>
  <a href="#" onclick="nav('modules',this)"><span class="icon">&#9881;</span> التحكم بالوحدات</a>
  <a href="#" onclick="nav('marketers',this)"><span class="icon">&#128279;</span> المسوقون</a>
  <a href="#" onclick="nav('leads',this)"><span class="icon">&#128231;</span> الزوّار المهتمّون <span id="leads-badge" style="display:none;background:#dc2626;color:#fff;border-radius:20px;padding:0 7px;font-size:11px;margin-inline-start:6px"></span></a>
  <a href="#" onclick="nav('tickets',this)"><span class="icon">&#127917;</span> الدعم</a>
  <div class="spacer"></div>
  <a href="/api/health" target="_blank"><span class="icon">&#128154;</span> الصحة</a>
  <a href="/api/admin/logout" style="color:#f87171"><span class="icon">&#128682;</span> خروج</a>
</div>
<div class="main">
  <div class="topbar">
    <h2 id="page-title">الرئيسية</h2>
    <div style="display:flex;gap:10px;align-items:center">
      <span id="clock" style="font-size:.8rem;color:#94a3b8"></span>
      <button class="btn btn-s" onclick="refreshAll()" title="تحديث">&#8635; تحديث</button>
      <a href="/api/admin/logout" class="btn btn-r">خروج</a>
    </div>
  </div>

  <div class="content">

  <!-- ═══════════ OVERVIEW ═══════════ -->
  <div id="pane-overview" class="pane active">
    <div class="stat-grid">
      <div class="stat"><div class="val" id="st-total">-</div><div class="lbl">إجمالي المنشآت</div></div>
      <div class="stat g"><div class="val" id="st-active">-</div><div class="lbl">نشطة</div></div>
      <div class="stat y"><div class="val" id="st-trial">-</div><div class="lbl">تجريبي</div></div>
      <div class="stat r"><div class="val" id="st-suspended">-</div><div class="lbl">موقوفة</div></div>
      <div class="stat p"><div class="val" id="st-sessions">-</div><div class="lbl">جلسات نشطة الآن</div></div>
      <div class="stat"><div class="val" id="st-revenue">-</div><div class="lbl">الإيرادات (ر.س)</div></div>
    </div>
    <div id="expiry-alerts"></div>
    <div class="card">
      <div class="card-hdr"><h3>آخر المنشآت المسجلة</h3></div>
      <table><thead><tr><th>المنشأة</th><th>الخطة</th><th>الحالة</th><th>تاريخ التسجيل</th></tr></thead>
      <tbody id="ov-recent"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ CLIENTS ═══════════ -->
  <div id="pane-clients" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>جميع المنشآت</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-p" onclick="openAddModal()">+ إضافة</button>
          <button class="btn btn-g" onclick="generateKey()">+ مفتاح تفعيل</button>
          <button class="btn" style="background:#fef3c7;color:#92400e;border-color:#fcd34d" onclick="openOwnerSetup()">&#128081; حساب المالك</button>
        </div>
      </div>
      <div id="key-result" style="display:none;background:#f0fdf4;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-weight:700;color:#16a34a;letter-spacing:2px;font-size:.9rem"></div>
      <div style="overflow-x:auto">
      <table><thead><tr>
        <th>المنشأة</th><th>الخطة</th><th>الحالة</th><th>انتهاء الاشتراك</th><th>تاريخ التسجيل</th><th>إجراءات</th>
      </tr></thead>
      <tbody id="clients-body"></tbody></table>
      </div>
    </div>
  </div>

  <!-- ═══════════ SESSIONS ═══════════ -->
  <div id="pane-sessions" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>الجلسات النشطة الآن</h3>
        <button class="btn btn-s" onclick="loadSessions()">&#8635; تحديث</button>
      </div>
      <table><thead><tr>
        <th>المنشأة</th><th>وقت الدخول</th><th>المدة</th><th>إجراء</th>
      </tr></thead>
      <tbody id="sessions-body"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ SUBSCRIPTIONS ═══════════ -->
  <div id="pane-subs" class="pane">
    <div class="card">
      <div class="card-hdr"><h3>إدارة الاشتراكات</h3><button class="btn btn-s" onclick="loadSubs()">&#8635; تحديث</button></div>
      <div style="overflow-x:auto">
      <table><thead><tr>
        <th>المنشأة</th><th>الخطة</th><th>الحالة</th><th>بداية</th><th>نهاية</th><th>المتبقي</th><th>السعر</th><th>تعديل</th>
      </tr></thead>
      <tbody id="subs-body"></tbody></table>
      </div>
    </div>
  </div>

  <!-- ═══════════ PACKAGES (public pricing) ═══════════ -->
  <div id="pane-packages" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>&#128176; أسعار الباقات المعروضة للزوار</h3>
        <div style="display:flex;gap:8px;align-items:center">
          <a href="/static/dheuof/packages.html" target="_blank" class="btn btn-s">&#128065; معاينة الصفحة</a>
          <button class="btn btn-s" onclick="loadPackages()">&#8635; تحديث</button>
        </div>
      </div>
      <p style="font-size:.8rem;color:#64748b;margin-bottom:16px">عدّل الأسعار والنصوص هنا — تظهر فوراً في صفحة الباقات العامة <code>/packages.html</code> بدون لمس الكود.</p>
      <div id="pkg-edit-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px"></div>
      <div style="margin-top:18px;padding-top:14px;border-top:1px solid #f1f5f9">
        <button class="btn btn-p" onclick="savePackages()">&#10003; حفظ الأسعار</button>
        <span id="pkg-saved" style="display:none;color:#16a34a;font-size:.8rem;margin-right:10px">&#10003; تم الحفظ — ظهرت في الصفحة العامة</span>
      </div>
    </div>
  </div>

  <!-- ═══════════ EMPLOYEES ═══════════ -->
  <div id="pane-employees" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>سجل الموظفين</h3>
        <div style="display:flex;gap:8px;align-items:center">
          <select id="emp-filter" onchange="loadEmployees()" style="padding:6px 10px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.8rem">
            <option value="">كل المنشآت</option>
          </select>
          <button class="btn btn-s" onclick="loadEmployees()">&#8635; تحديث</button>
        </div>
      </div>
      <table><thead><tr>
        <th>المنشأة</th><th>الموظف</th><th>الدور</th><th>آخر نشاط</th><th>عدد المهام</th>
      </tr></thead>
      <tbody id="emp-body"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ MODULES ═══════════ -->
  <div id="pane-modules" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>التحكم بالوحدات لكل منشأة</h3>
        <select id="mod-client-sel" onchange="loadModules()" style="padding:6px 10px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.8rem">
          <option value="">-- اختر منشأة --</option>
        </select>
      </div>
      <div id="modules-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-top:4px"></div>
      <div id="modules-save-row" style="display:none;margin-top:16px;padding-top:14px;border-top:1px solid #f1f5f9">
        <button class="btn btn-p" onclick="saveModules()">&#10003; حفظ التغييرات</button>
        <span id="mod-saved" style="display:none;color:#16a34a;font-size:.8rem;margin-right:10px">&#10003; تم الحفظ</span>
      </div>
    </div>
  </div>

  <!-- ═══════════ MARKETERS ═══════════ -->
  <div id="pane-marketers" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>&#128279; المسوقون وروابطهم التسويقية</h3>
        <div style="display:flex;gap:8px">
          <button class="btn btn-p" onclick="openAddMktr()">+ إضافة مسوق</button>
          <button class="btn btn-s" onclick="loadMarketers()">&#8635; تحديث</button>
        </div>
      </div>
      <div id="mktr-link-info" style="display:none;background:#f0fdf4;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:.8rem;color:#166534;word-break:break-all"></div>
      <table><thead><tr>
        <th>اسم المسوق</th><th>كود الإحالة</th><th>رابط التسجيل</th><th>التسجيلات</th><th>العمولة %</th><th>الحالة</th><th>إجراءات</th>
      </tr></thead>
      <tbody id="mktr-body"></tbody></table>
    </div>
  </div>

  <!-- ═══════════ TICKETS ═══════════ -->
  <div id="pane-leads" class="pane">
    <div class="card">
      <div class="card-hdr">
        <h3>الزوّار المهتمّون <span id="leads-count" style="color:#64748b;font-weight:400"></span></h3>
        <div>
          <select id="leads-filter" onchange="loadLeads()" style="padding:6px 10px;border:1px solid #cbd5e1;border-radius:6px;font-family:inherit">
            <option value="">الكل</option>
            <option value="new">جديد</option>
            <option value="contacted">تُوُوصل معه</option>
            <option value="converted">اشترك</option>
            <option value="dropped">مُهمَل</option>
          </select>
          <button class="btn btn-s" onclick="loadLeads()">&#8635; تحديث</button>
        </div>
      </div>
      <table><thead><tr>
        <th>الاسم</th><th>الجوال</th><th>البريد</th><th>المنشأة</th>
        <th>المدينة</th><th>الغرف</th><th>الرسالة</th><th>التاريخ</th><th>الحالة</th>
      </tr></thead>
      <tbody id="leads-body"></tbody></table>
    </div>
  </div>

  <div id="pane-tickets" class="pane">
    <div class="card">
      <div class="card-hdr"><h3>تذاكر الدعم</h3><button class="btn btn-s" onclick="loadTickets()">&#8635; تحديث</button></div>
      <table><thead><tr>
        <th>المنشأة</th><th>الموضوع</th><th>الحالة</th><th>التاريخ</th><th>رد</th>
      </tr></thead>
      <tbody id="tickets-body"></tbody></table>
    </div>
  </div>

  </div>
</div>

<!-- Modal: Add Client -->
<div class="modal-bg" id="modal-add">
  <div class="modal">
    <h4>إضافة منشأة جديدة</h4>
    <div class="fg"><label>معرف المنشأة (ID)</label><input id="nc-id" placeholder="hotel-001"></div>
    <div class="fg"><label>اسم المنشأة</label><input id="nc-name" placeholder="فندق النخبة"></div>
    <div class="fg"><label>البريد الإلكتروني</label><input id="nc-email" type="email" placeholder="hotel@example.com"></div>
    <div class="fg"><label>كلمة المرور</label><input id="nc-pass" type="password"></div>
    <div class="fg"><label>الخطة</label>
      <select id="nc-plan">
        <option value="trial">تجريبي (trial)</option>
        <option value="starter">مبدئي (starter)</option>
        <option value="operations">تشغيلي (operations)</option>
        <option value="professional">احترافي (professional)</option>
        <option value="enterprise">مؤسسي (enterprise)</option>
      </select>
    </div>
    <div id="nc-err" style="display:none;color:#dc2626;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-p" style="flex:1" onclick="addClient()">إضافة</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-add')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Owner Account Setup -->
<div class="modal-bg" id="modal-owner">
  <div class="modal">
    <h4 style="color:#92400e">&#128081; إعداد حساب المالك</h4>
    <p style="font-size:.8rem;color:#6b7280;margin-bottom:14px">يُنشئ أو يُحدِّث حساباً بخطة Enterprise مدى الحياة مع تمييز خاص في لوحة التحكم.</p>
    <div class="fg"><label>معرف الحساب (ID)</label><input id="own-id" placeholder="dheuof-owner" value="dheuof"></div>
    <div class="fg"><label>اسم المنشأة</label><input id="own-name" placeholder="ضيوف للاستضافة الذكية" value="ضيوف للاستضافة الذكية"></div>
    <div class="fg"><label>البريد الإلكتروني</label><input id="own-email" type="email" placeholder="abdulellah.sh11@gmail.com" value="abdulellah.sh11@gmail.com"></div>
    <div class="fg"><label>كلمة المرور</label><input id="own-pass" type="password" placeholder="اختر كلمة مرور قوية"></div>
    <div id="own-result" style="display:none;padding:10px;border-radius:8px;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn" style="flex:1;background:#fef3c7;color:#92400e;border-color:#fcd34d" onclick="saveOwnerSetup()">&#10003; حفظ حساب المالك</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-owner')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Edit Subscription -->
<div class="modal-bg" id="modal-sub">
  <div class="modal">
    <h4>تعديل اشتراك: <span id="sub-edit-name"></span></h4>
    <input type="hidden" id="sub-edit-cid">
    <div class="fg-row">
      <div class="fg"><label>الخطة</label>
        <select id="sub-plan">
          <option value="trial">trial</option>
          <option value="starter">starter</option>
          <option value="operations">operations</option>
          <option value="professional">professional</option>
          <option value="enterprise">enterprise</option>
        </select>
      </div>
      <div class="fg"><label>الحالة</label>
        <select id="sub-status">
          <option value="trial">تجريبي</option>
          <option value="active">نشط</option>
          <option value="suspended">موقوف</option>
          <option value="expired">منتهي</option>
        </select>
      </div>
    </div>
    <div class="fg-row">
      <div class="fg"><label>تاريخ البداية</label><input type="date" id="sub-start"></div>
      <div class="fg"><label>تاريخ الانتهاء</label><input type="date" id="sub-end"></div>
    </div>
    <div class="fg"><label>السعر الشهري (ر.س)</label><input type="number" id="sub-price" min="0" step="0.01"></div>
    <div id="sub-err" style="display:none;color:#dc2626;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px;margin-top:16px">
      <button class="btn btn-p" style="flex:1" onclick="saveSub()">حفظ</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-sub')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Client Detail (employees + password reset) -->
<div class="modal-bg" id="modal-client-detail">
  <div class="modal" style="max-width:680px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px">
      <h4 id="detail-title" style="margin:0">تفاصيل المنشأة</h4>
      <button onclick="closeModal('modal-client-detail')" style="background:none;border:none;cursor:pointer;font-size:1.3rem;color:#94a3b8">&#10005;</button>
    </div>
    <!-- Manager section -->
    <div style="background:#f8fafc;border-radius:10px;padding:14px 16px;margin-bottom:16px">
      <div style="font-size:.8rem;font-weight:700;color:#0F2640;margin-bottom:10px">&#128272; بيانات المدير / الدخول</div>
      <div class="fg-row">
        <div class="fg"><label>كلمة مرور جديدة</label><input type="password" id="mgr-pass" placeholder="اتركها فارغة للإبقاء"></div>
        <div class="fg" style="display:flex;align-items:flex-end">
          <button class="btn btn-y" style="width:100%" onclick="resetManagerPass()">&#128274; تغيير كلمة المرور</button>
        </div>
      </div>
      <div id="mgr-msg" style="font-size:.8rem;margin-top:6px;display:none"></div>
    </div>
    <!-- API keys section -->
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:10px;padding:14px 16px;margin-bottom:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <div style="font-size:.8rem;font-weight:700;color:#0F2640">&#128273; مفاتيح API لهذه المنشأة</div>
        <button class="btn btn-p" style="padding:6px 12px;font-size:.78rem" onclick="issueApiKey()">&#10133; توليد مفتاح</button>
      </div>
      <div style="font-size:.72rem;color:#64748b;margin-bottom:8px">المفتاح مرتبطٌ برقم المنشأة، ويظهر خاماً مرّةً واحدة فقط عند التوليد.</div>
      <div id="apikey-new" style="display:none;background:#052e16;color:#bbf7d0;border-radius:8px;padding:10px 12px;margin-bottom:10px;font-family:monospace;font-size:.8rem;word-break:break-all"></div>
      <div id="apikey-list" style="font-size:.78rem;color:#64748b">جاري التحميل...</div>
    </div>
    <!-- Employees section -->
    <div style="font-size:.8rem;font-weight:700;color:#0F2640;margin-bottom:10px">&#128188; الموظفون في هذه المنشأة</div>
    <div style="overflow-x:auto;max-height:280px;overflow-y:auto">
    <table><thead><tr><th>الاسم</th><th>الدور</th><th>آخر نشاط</th><th>عدد المهام</th></tr></thead>
    <tbody id="detail-emp-body"></tbody></table>
    </div>
    <input type="hidden" id="detail-cid">
  </div>
</div>

<!-- Modal: Add Marketer -->
<div class="modal-bg" id="modal-mktr">
  <div class="modal">
    <h4>إضافة مسوق جديد</h4>
    <div class="fg"><label>الاسم</label><input id="mk-name" placeholder="اسم المسوق"></div>
    <div class="fg-row">
      <div class="fg"><label>كود الإحالة (اختياري)</label><input id="mk-code" placeholder="ABC123 — يُولَّد تلقائياً"></div>
      <div class="fg"><label>نسبة العمولة %</label><input type="number" id="mk-comm" value="10" min="0" max="100"></div>
    </div>
    <div class="fg-row">
      <div class="fg"><label>رقم الهاتف</label><input id="mk-phone" placeholder="+9665xxxxxxxx"></div>
      <div class="fg"><label>البريد الإلكتروني</label><input id="mk-email" placeholder="marketer@email.com"></div>
    </div>
    <div class="fg"><label>ملاحظات</label><input id="mk-notes" placeholder="ملاحظات اختيارية"></div>
    <div id="mk-err" style="display:none;color:#dc2626;font-size:.8rem;margin-bottom:10px"></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-p" style="flex:1" onclick="addMarketer()">إضافة</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-mktr')">إلغاء</button>
    </div>
  </div>
</div>

<!-- Modal: Marketer Referrals -->
<div class="modal-bg" id="modal-refs">
  <div class="modal" style="max-width:640px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h4 id="refs-title" style="margin:0">تسجيلات المسوق</h4>
      <button onclick="closeModal('modal-refs')" style="background:none;border:none;cursor:pointer;font-size:1.3rem;color:#94a3b8">&#10005;</button>
    </div>
    <div id="refs-link" style="background:#f0fdf4;padding:10px 14px;border-radius:8px;margin-bottom:14px;font-size:.8rem;color:#166534;word-break:break-all"></div>
    <table><thead><tr><th>المنشأة</th><th>الخطة</th><th>تاريخ التسجيل</th></tr></thead>
    <tbody id="refs-body"></tbody></table>
  </div>
</div>

<!-- Modal: Ticket Reply -->
<div class="modal-bg" id="modal-ticket">
  <div class="modal">
    <h4>الرد على التذكرة</h4>
    <input type="hidden" id="tk-id">
    <div class="fg"><label>الرد</label><textarea id="tk-reply" rows="4" style="width:100%;padding:8px 12px;border:1.5px solid #e2e8f0;border-radius:8px;font-size:.875rem;resize:vertical"></textarea></div>
    <div style="display:flex;gap:10px">
      <button class="btn btn-p" style="flex:1" onclick="sendReply()">إرسال</button>
      <button class="btn btn-s" style="flex:1" onclick="closeModal('modal-ticket')">إلغاء</button>
    </div>
  </div>
</div>

<script>
const PLANS={trial:'تجريبي',starter:'مبدئي',operations:'تشغيلي',professional:'احترافي',enterprise:'مؤسسي'};
const STATUS_AR={active:'نشط',trial:'تجريبي',suspended:'موقوف',expired:'منتهي'};
const STATUS_CLS={active:'bg',trial:'by',suspended:'br',expired:'br'};
let _clients=[];

function tick(){
  const n=new Date();
  document.getElementById('clock').textContent=n.toLocaleDateString('ar-SA',{weekday:'short',year:'numeric',month:'short',day:'numeric'})+' '+n.toLocaleTimeString('ar-SA');
}
setInterval(tick,1000);tick();

function nav(id,el){
  document.querySelectorAll('.pane').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(a=>a.classList.remove('active'));
  document.getElementById('pane-'+id).classList.add('active');
  if(el){el.classList.add('active');}
  const titles={overview:'الرئيسية',clients:'المنشآت',sessions:'الجلسات النشطة',subs:'الاشتراكات',packages:'أسعار الباقات',employees:'الموظفون',modules:'التحكم بالوحدات',tickets:'تذاكر الدعم',marketers:'المسوقون',leads:'الزوّار المهتمّون'};
  document.getElementById('page-title').textContent=titles[id]||id;
  if(id==='clients')loadClients();
  else if(id==='sessions')loadSessions();
  else if(id==='subs')loadSubs();
  else if(id==='packages')loadPackages();
  else if(id==='employees')loadEmployees();
  else if(id==='modules')initModulesPane();
  else if(id==='leads')loadLeads();
  else if(id==='tickets')loadTickets();
  else if(id==='marketers')loadMarketers();
}

function refreshAll(){loadOverview();const active=document.querySelector('.pane.active')?.id?.replace('pane-','');if(active&&active!=='overview')nav(active);}

function openModal(id){document.getElementById(id).classList.add('open');}
function closeModal(id){document.getElementById(id).classList.remove('open');}
function openAddModal(){['nc-id','nc-name','nc-email','nc-pass'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});document.getElementById('nc-err').style.display='none';openModal('modal-add');}
function openOwnerSetup(){document.getElementById('own-result').style.display='none';openModal('modal-owner');}
async function saveOwnerSetup(){
  const cid=document.getElementById('own-id').value.trim();
  const name=document.getElementById('own-name').value.trim();
  const email=document.getElementById('own-email').value.trim();
  const pass=document.getElementById('own-pass').value;
  const res=document.getElementById('own-result');
  if(!cid||!name||!pass){res.style.display='block';res.style.background='#fee2e2';res.style.color='#dc2626';res.textContent='جميع الحقول مطلوبة';return;}
  const r=await fetch('/api/admin/owner-setup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:cid,name,email,password:pass})});
  const d=await r.json();
  if(d.success){res.style.display='block';res.style.background='#f0fdf4';res.style.color='#16a34a';res.textContent='✓ تم إنشاء حساب المالك — ينتهي الاشتراك: '+d.sub_end;loadClients();loadSubs();}
  else{res.style.display='block';res.style.background='#fee2e2';res.style.color='#dc2626';res.textContent=d.error||'خطأ';}
}

// ─── Overview ───────────────────────────────────────────────
async function loadOverview(){
  const [cr,sr]=await Promise.all([
    fetch('/api/admin/clients').then(r=>r.json()).catch(()=>({})),
    fetch('/api/admin/sessions').then(r=>r.json()).catch(()=>({}))
  ]);
  const clients=cr.clients||[];_clients=clients;
  const total=clients.length;
  const active=clients.filter(c=>c.status==='active').length;
  const trial=clients.filter(c=>c.status==='trial').length;
  const susp=clients.filter(c=>c.status==='suspended').length;
  const sessions=(sr.sessions||[]).length;
  document.getElementById('st-total').textContent=total;
  document.getElementById('st-active').textContent=active;
  document.getElementById('st-trial').textContent=trial;
  document.getElementById('st-suspended').textContent=susp;
  document.getElementById('st-sessions').textContent=sessions;
  // revenue from subscriptions
  let rev=0;
  clients.forEach(c=>{if(c.sub_price)rev+=parseFloat(c.sub_price)||0;});
  document.getElementById('st-revenue').textContent=rev.toLocaleString('ar-SA',{minimumFractionDigits:0});
  // expiry alerts
  const alerts=document.getElementById('expiry-alerts');
  alerts.innerHTML='';
  const today=new Date();
  clients.forEach(c=>{
    if(c.sub_end){
      const end=new Date(c.sub_end);
      const days=Math.ceil((end-today)/86400000);
      if(days<=14&&days>=0){
        alerts.innerHTML+=`<div class="alert-exp">⚠️ <strong>${c.name||c.id}</strong> — اشتراكه ينتهي خلال <strong>${days}</strong> يوم (${c.sub_end})</div>`;
      }else if(days<0){
        alerts.innerHTML+=`<div class="alert-exp" style="background:#fee2e2;border-color:#fca5a5;color:#7f1d1d">🔴 <strong>${c.name||c.id}</strong> — اشتراكه انتهى منذ ${Math.abs(days)} يوم</div>`;
      }
    }
  });
  // recent
  const recent=[...clients].sort((a,b)=>new Date(b.created_at||0)-new Date(a.created_at||0)).slice(0,5);
  document.getElementById('ov-recent').innerHTML=recent.map(c=>{
    const sc=STATUS_CLS[c.status]||'bb';
    return `<tr><td><strong>${c.name||c.id}</strong><br><small style="color:#94a3b8">${c.id}</small></td>
      <td><span class="badge bb">${PLANS[c.plan]||c.plan||'—'}</span></td>
      <td><span class="badge ${sc}">${STATUS_AR[c.status]||c.status}</span></td>
      <td>${(c.created_at||'').substring(0,10)||'—'}</td></tr>`;
  }).join('')||'<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:24px">لا توجد بيانات</td></tr>';
}

// ─── Clients ────────────────────────────────────────────────
async function loadClients(){
  const r=await fetch('/api/admin/clients').then(r=>r.json()).catch(()=>({}));
  const clients=r.clients||[];_clients=clients;
  document.getElementById('clients-body').innerHTML=clients.map(c=>{
    const sc=STATUS_CLS[c.status]||'bb';
    const end=c.sub_end?`<span style="font-weight:600">${c.sub_end}</span>`:'<span style="color:#94a3b8">—</span>';
    const days=c.sub_end?Math.ceil((new Date(c.sub_end)-new Date())/86400000):null;
    const daysTag=days!==null?(days<0?`<span class="tag" style="background:#fee2e2;color:#dc2626">منتهي</span>`:(days<=14?`<span class="tag" style="background:#fef3c7;color:#92400e">${days}y</span>`:`<span class="tag" style="background:#dcfce7;color:#16a34a">${days}y</span>`)): '';
    const ownerBadge=c.is_owner?'<span class="badge" style="background:#fef3c7;color:#92400e;margin-right:4px">&#128081; مالك</span>':''
    return `<tr${c.is_owner?' style="background:#fffbeb"':''}>
      <td><strong>${c.name||c.id}</strong>${ownerBadge}<br><small style="color:#94a3b8;font-size:11px">${c.id}</small>${c.email?`<br><small style="color:#6b7280;font-size:10px">&#9993; ${c.email}</small>`:''}</td>
      <td><span class="badge bb">${PLANS[c.plan]||c.plan||'—'}</span></td>
      <td><span class="badge ${sc}">${STATUS_AR[c.status]||c.status}</span></td>
      <td>${end} ${daysTag}</td>
      <td>${(c.created_at||'').substring(0,10)||'—'}</td>
      <td style="white-space:nowrap">
        <button class="btn btn-p" onclick="openClientDetail('${c.id}')" style="margin-left:4px">&#128065; تفاصيل</button>
        <button class="btn btn-s" onclick="editSub('${c.id}')" style="margin-left:4px">&#9998; اشتراك</button>
        <button class="btn btn-s" onclick="toggleClient('${c.id}')" style="margin-left:4px">تبديل</button>
        <button class="btn btn-r" onclick="deleteClient('${c.id}')">حذف</button>
      </td>
    </tr>`;
  }).join('')||'<tr><td colspan="6" style="text-align:center;color:#94a3b8;padding:32px">لا توجد منشآت</td></tr>';
}

async function addClient(){
  const id=document.getElementById('nc-id').value.trim();
  const name=document.getElementById('nc-name').value.trim();
  const email=document.getElementById('nc-email').value.trim();
  const pass=document.getElementById('nc-pass').value;
  const plan=document.getElementById('nc-plan').value;
  const err=document.getElementById('nc-err');
  if(!id||!name||!pass){err.textContent='جميع الحقول مطلوبة';err.style.display='block';return;}
  const r=await fetch('/api/admin/clients',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,name,email,password:pass,plan})});
  const d=await r.json();
  if(d.success){closeModal('modal-add');loadClients();loadOverview();}
  else{err.textContent=d.error||'خطأ';err.style.display='block';}
}

async function toggleClient(id){
  await fetch('/api/admin/clients/'+id+'/toggle',{method:'POST'});
  loadClients();loadOverview();
}

async function deleteClient(id){
  if(!confirm('هل تريد حذف هذه المنشأة نهائياً؟'))return;
  await fetch('/api/admin/clients/'+id,{method:'DELETE'});
  loadClients();loadOverview();
}

async function generateKey(){
  const plan=prompt('الخطة (trial/starter/operations/professional/enterprise):','trial');
  if(!plan)return;
  const days=parseInt(prompt('عدد الأيام:','30'))||30;
  const r=await fetch('/api/admin/keys/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({plan,days})});
  const d=await r.json();
  if(d.key){const el=document.getElementById('key-result');el.style.display='block';el.textContent='🔑 المفتاح: '+d.key;}
}

// ─── Sessions ───────────────────────────────────────────────
async function loadSessions(){
  const r=await fetch('/api/admin/sessions').then(r=>r.json()).catch(()=>({}));
  const sessions=r.sessions||[];
  document.getElementById('st-sessions').textContent=sessions.length;
  const now=new Date();
  document.getElementById('sessions-body').innerHTML=sessions.map(s=>{
    const created=new Date(s.created_at);
    const mins=Math.floor((now-created)/60000);
    const dur=mins<60?`${mins} دقيقة`:`${Math.floor(mins/60)}س ${mins%60}د`;
    return `<tr>
      <td><strong>${s.client_name||s.client_id}</strong><br><small style="color:#94a3b8">${s.client_id}</small></td>
      <td>${s.created_at.replace('T',' ').substring(0,19)}</td>
      <td><span class="dot dot-g"></span>${dur}</td>
      <td><button class="btn btn-r" style="padding:4px 10px;font-size:.75rem" onclick="revokeSession('${s.token_prefix}')">إنهاء</button></td>
    </tr>`;
  }).join('')||'<tr><td colspan="4" style="text-align:center;color:#94a3b8;padding:32px">لا توجد جلسات نشطة</td></tr>';
}

async function revokeSession(prefix){
  if(!confirm('هل تريد إنهاء هذه الجلسة؟'))return;
  await fetch('/api/admin/sessions/'+prefix+'/revoke',{method:'POST'});
  loadSessions();
}

// ─── Subscriptions ──────────────────────────────────────────
async function loadSubs(){
  const r=await fetch('/api/admin/subscriptions').then(r=>r.json()).catch(()=>({}));
  const subs=r.subscriptions||[];
  const today=new Date();
  document.getElementById('subs-body').innerHTML=subs.map(s=>{
    const end=s.sub_end?new Date(s.sub_end):null;
    const days=end?Math.ceil((end-today)/86400000):null;
    let daysHtml='—';
    if(days!==null){
      if(days<0)daysHtml=`<span style="color:#dc2626;font-weight:600">انتهى منذ ${Math.abs(days)}ي</span>`;
      else if(days<=14)daysHtml=`<span style="color:#d97706;font-weight:600">${days} يوم</span>`;
      else daysHtml=`<span style="color:#16a34a;font-weight:600">${days} يوم</span>`;
    }
    const sc=STATUS_CLS[s.status]||'bb';
    const ownerTag=s.is_owner?'<span class="badge" style="background:#fef3c7;color:#92400e;margin-right:4px">&#128081;</span>':'';
    return `<tr${s.is_owner?' style="background:#fffbeb"':''}>
      <td><strong>${ownerTag}${s.name||s.client_id}</strong><br><small style="color:#94a3b8">${s.client_id}</small></td>
      <td><span class="badge bb">${PLANS[s.plan]||s.plan||'—'}</span></td>
      <td><span class="badge ${sc}">${STATUS_AR[s.status]||s.status}</span></td>
      <td>${s.sub_start||'—'}</td>
      <td>${s.sub_end||'—'}</td>
      <td>${daysHtml}</td>
      <td>${s.price?parseFloat(s.price).toLocaleString('ar-SA'):'—'} ر.س</td>
      <td><button class="btn btn-y" onclick="editSub('${s.client_id}')">&#9998; تعديل</button></td>
    </tr>`;
  }).join('')||'<tr><td colspan="8" style="text-align:center;color:#94a3b8;padding:32px">لا توجد اشتراكات</td></tr>';
}

function editSub(cid){
  const c=_clients.find(x=>x.id===cid)||{id:cid};
  document.getElementById('sub-edit-cid').value=cid;
  document.getElementById('sub-edit-name').textContent=c.name||cid;
  document.getElementById('sub-plan').value=c.plan||'trial';
  document.getElementById('sub-status').value=c.status||'trial';
  document.getElementById('sub-start').value=c.sub_start||'';
  document.getElementById('sub-end').value=c.sub_end||'';
  document.getElementById('sub-price').value=c.sub_price||'';
  document.getElementById('sub-err').style.display='none';
  openModal('modal-sub');
}

async function saveSub(){
  const cid=document.getElementById('sub-edit-cid').value;
  const body={
    plan:document.getElementById('sub-plan').value,
    status:document.getElementById('sub-status').value,
    sub_start:document.getElementById('sub-start').value,
    sub_end:document.getElementById('sub-end').value,
    sub_price:parseFloat(document.getElementById('sub-price').value)||0
  };
  const r=await fetch('/api/admin/subscriptions/'+cid,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.success){closeModal('modal-sub');loadClients();loadSubs();loadOverview();}
  else{const e=document.getElementById('sub-err');e.textContent=d.error||'خطأ';e.style.display='block';}
}

// ─── Public Packages (pricing) ──────────────────────────────
let _packages=[];
async function loadPackages(){
  const r=await fetch('/api/packages').then(r=>r.json()).catch(()=>({}));
  _packages=r.packages||[];
  const esc=s=>String(s==null?'':s).replace(/"/g,'&quot;');
  document.getElementById('pkg-edit-grid').innerHTML=_packages.map((p,i)=>`
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:16px">
      <div style="font-size:.7rem;color:#94a3b8;font-family:monospace;margin-bottom:8px">${esc(p.id)}</div>
      <div class="fg"><label>اسم الباقة</label><input data-pk="${i}" data-pf="name_ar" value="${esc(p.name_ar)}"></div>
      <div class="fg-row">
        <div class="fg"><label>السعر</label><input data-pk="${i}" data-pf="price" value="${esc(p.price)}" placeholder="٢٬٤٠٠ أو حسب الطلب"></div>
        <div class="fg"><label>العملة</label><input data-pk="${i}" data-pf="currency" value="${esc(p.currency)}" placeholder="ر.س"></div>
      </div>
      <div class="fg-row">
        <div class="fg"><label>المدة</label><input data-pk="${i}" data-pf="period" value="${esc(p.period)}" placeholder="/شهر"></div>
        <div class="fg"><label>الخصم ٪ (اختياري)</label><input data-pk="${i}" data-pf="discount_percent" type="number" min="0" max="100" value="${esc(p.discount_percent||0)}" placeholder="0"></div>
      </div>
      ${p.price_after && p.discount_percent>0?`<div style="font-size:.78rem;color:#10b981;margin:-4px 0 8px">السعر بعد الخصم: <strong>${esc(p.price_after)} ${esc(p.currency)}</strong> <span style="color:#94a3b8;text-decoration:line-through">${esc(p.price_original)}</span></div>`:''}
      <div class="fg"><label>ملاحظة التوفير (اختياري)</label><input data-pk="${i}" data-pf="save_note" value="${esc(p.save_note)}" placeholder="يُحسب تلقائياً عند وضع خصم"></div>
      <div class="fg"><label>نص الزر</label><input data-pk="${i}" data-pf="cta" value="${esc(p.cta)}" placeholder="ابدأ التجربة"></div>
    </div>`).join('');
  document.getElementById('pkg-saved').style.display='none';
}

async function savePackages(){
  document.querySelectorAll('#pkg-edit-grid input[data-pk]').forEach(inp=>{
    const i=+inp.getAttribute('data-pk');const f=inp.getAttribute('data-pf');
    if(_packages[i])_packages[i][f]=inp.value;
  });
  const r=await fetch('/api/admin/packages',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({packages:_packages})});
  const d=await r.json();
  if(d.success){_packages=d.packages||_packages;const s=document.getElementById('pkg-saved');s.style.display='inline';setTimeout(()=>s.style.display='none',4000);}
  else alert(d.error||'خطأ في الحفظ');
}

// ─── Employees ──────────────────────────────────────────────
async function loadEmployees(){
  const filterCid=document.getElementById('emp-filter').value;
  const url='/api/admin/employees'+(filterCid?'?client_id='+filterCid:'');
  const r=await fetch(url).then(r=>r.json()).catch(()=>({}));
  const emps=r.employees||[];
  // populate filter
  const sel=document.getElementById('emp-filter');
  const cur=sel.value;
  if(sel.options.length<=1){
    _clients.forEach(c=>{const o=document.createElement('option');o.value=c.id;o.textContent=c.name||c.id;sel.appendChild(o);});
    sel.value=cur;
  }
  document.getElementById('emp-body').innerHTML=emps.map(e=>{
    return `<tr>
      <td><strong>${e.client_name||e.client_id}</strong></td>
      <td>${e.name||'—'}</td>
      <td><span class="badge bb">${e.role||'—'}</span></td>
      <td>${e.last_active?(e.last_active.replace('T',' ').substring(0,19)):'—'}</td>
      <td>${e.task_count||0}</td>
    </tr>`;
  }).join('')||'<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:32px">لا توجد بيانات</td></tr>';
}

// ─── Tickets ────────────────────────────────────────────────
// ── الزوّار المهتمّون ──────────────────────────────────────────
// ما يكتبه الزائر بيده في نموذج «تواصل معنا» — لا تتبّعٌ صامت.
function escLead(v){
  return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
const LEAD_STATUS={new:'جديد',contacted:'تُوُوصل معه',converted:'اشترك',dropped:'مُهمَل'};

async function loadLeads(){
  const f=document.getElementById('leads-filter').value;
  const r=await fetch('/api/admin/leads'+(f?'?status='+encodeURIComponent(f):''))
    .then(r=>r.json()).catch(()=>({}));
  const rows=r.data||[];
  const counts=r.counts||{};
  const body=document.getElementById('leads-body');

  const badge=document.getElementById('leads-badge');
  if(badge){
    const n=counts.new||0;
    badge.textContent=n; badge.style.display=n?'inline-block':'none';
  }
  document.getElementById('leads-count').textContent =
    rows.length ? '· '+rows.length+' سجل' : '';

  if(!rows.length){
    body.innerHTML='<tr><td colspan="9" style="text-align:center;padding:26px;color:#64748b">لا زوّار سجّلوا اهتمامهم بعد</td></tr>';
    return;
  }
  body.innerHTML=rows.map(l=>{
    const cls={new:'br',contacted:'bw',converted:'bg',dropped:''}[l.status]||'';
    const opts=Object.keys(LEAD_STATUS).map(k=>
      `<option value="${k}"${k===l.status?' selected':''}>${LEAD_STATUS[k]}</option>`).join('');
    return `<tr>
      <td><strong>${escLead(l.full_name)}</strong></td>
      <td dir="ltr">${escLead(l.phone||'—')}</td>
      <td dir="ltr">${escLead(l.email||'—')}</td>
      <td>${escLead(l.hotel_name||'—')}</td>
      <td>${escLead(l.city||'—')}</td>
      <td>${l.rooms||'—'}</td>
      <td style="max-width:220px">${escLead(l.message||'—')}</td>
      <td>${(l.created_at||'').substring(0,10)}</td>
      <td><span class="badge ${cls}">${LEAD_STATUS[l.status]||l.status}</span>
          <select onchange="setLeadStatus(${l.id},this.value)"
            style="margin-top:4px;padding:2px 6px;border:1px solid #cbd5e1;border-radius:5px;font-family:inherit;font-size:.72rem">
            ${opts}
          </select></td>
    </tr>`;
  }).join('');
}

async function setLeadStatus(id,status){
  const r=await fetch('/api/admin/leads/'+id,
    {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})})
    .then(r=>r.json()).catch(()=>({}));
  if(r.success)loadLeads();
  else alert('تعذّر تحديث الحالة');
}

async function loadTickets(){
  const r=await fetch('/api/admin/tickets').then(r=>r.json()).catch(()=>({}));
  const tickets=r.tickets||[];
  document.getElementById('tickets-body').innerHTML=tickets.map(t=>{
    const sc=t.status==='open'?'br':'bg';
    return `<tr>
      <td>${t.client_id||'—'}</td>
      <td>${t.subject||'—'}</td>
      <td><span class="badge ${sc}">${t.status==='open'?'مفتوح':'مغلق'}</span></td>
      <td>${(t.created_at||'').substring(0,10)}</td>
      <td><button class="btn btn-s" style="padding:4px 10px;font-size:.75rem" onclick="openReply('${t.id}')">رد</button></td>
    </tr>`;
  }).join('')||'<tr><td colspan="5" style="text-align:center;color:#94a3b8;padding:32px">لا توجد تذاكر</td></tr>';
}

function openReply(id){document.getElementById('tk-id').value=id;document.getElementById('tk-reply').value='';openModal('modal-ticket');}
async function sendReply(){
  const id=document.getElementById('tk-id').value;
  const reply=document.getElementById('tk-reply').value.trim();
  if(!reply)return;
  await fetch('/api/admin/tickets/reply',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,reply})});
  closeModal('modal-ticket');loadTickets();
}

// ─── Client Detail (Manager + Employees) ────────────────────
async function openClientDetail(cid){
  const c=_clients.find(x=>x.id===cid)||{id:cid,name:cid};
  document.getElementById('detail-cid').value=cid;
  document.getElementById('detail-title').textContent='تفاصيل: '+(c.name||cid);
  document.getElementById('mgr-pass').value='';
  document.getElementById('mgr-msg').style.display='none';
  document.getElementById('detail-emp-body').innerHTML='<tr><td colspan="4" style="text-align:center;padding:20px;color:#94a3b8">جاري التحميل...</td></tr>';
  openModal('modal-client-detail');
  // load employees for this client
  const r=await fetch('/api/admin/employees?client_id='+cid).then(r=>r.json()).catch(()=>({}));
  const emps=r.employees||[];
  document.getElementById('detail-emp-body').innerHTML=emps.length?emps.map(e=>`<tr>
    <td><strong>${e.name||'—'}</strong></td>
    <td><span class="badge bb">${e.role||'—'}</span></td>
    <td>${e.last_active?(e.last_active.replace('T',' ').substring(0,19)):'لم يسجل نشاط'}</td>
    <td>${e.task_count||0}</td>
  </tr>`).join(''):'<tr><td colspan="4" style="text-align:center;padding:20px;color:#94a3b8">لا يوجد موظفون مسجلون</td></tr>';
  document.getElementById('apikey-new').style.display='none';
  loadApiKeys();
}

// ─── مفاتيح API لكل منشأة ────────────────────────────────────
async function loadApiKeys(){
  const cid=document.getElementById('detail-cid').value;
  const box=document.getElementById('apikey-list');
  box.textContent='جاري التحميل...';
  const r=await fetch('/api/admin/clients/'+cid+'/api-keys').then(r=>r.json()).catch(()=>({}));
  if(!r.success){box.textContent=r.detail||'تعذّر تحميل المفاتيح';return;}
  const keys=r.keys||[];
  if(!keys.length){box.textContent='لا توجد مفاتيح — ولّد أول مفتاح لهذه المنشأة.';return;}
  box.innerHTML=keys.map(k=>`<div style="display:flex;justify-content:space-between;align-items:center;background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:8px 10px;margin-bottom:6px">
    <div><code style="font-size:.75rem">${k.key_hint||'••••'}</code>
      <span style="font-size:.68rem;color:${k.active?'#059669':'#dc2626'};margin-right:6px">${k.active?'● فعّال':'○ مُبطَل'}</span>
      <div style="font-size:.66rem;color:#94a3b8">${(k.scopes||[]).join(' · ')||'—'}</div></div>
    ${k.active?`<button class="btn btn-d" style="padding:4px 10px;font-size:.72rem" onclick="revokeApiKey(${k.id})">إبطال</button>`:''}
  </div>`).join('');
}

async function issueApiKey(){
  const cid=document.getElementById('detail-cid').value;
  const name=prompt('اسمٌ للمفتاح (اختياري) — مثل: تكامل المحاسبة');
  if(name===null)return;
  const r=await fetch('/api/admin/clients/'+cid+'/api-keys',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:name||''})});
  const d=await r.json();
  if(!d.success){alert(d.detail||'تعذّر توليد المفتاح');return;}
  const box=document.getElementById('apikey-new');
  box.textContent='المفتاح (انسخه الآن — لن يظهر مجدداً): '+d.issued.api_key;
  box.style.display='block';
  loadApiKeys();
}

async function revokeApiKey(keyId){
  if(!confirm('إبطال هذا المفتاح؟ ستتوقف البرامج المرتبطة به فوراً.'))return;
  const cid=document.getElementById('detail-cid').value;
  const r=await fetch('/api/admin/clients/'+cid+'/api-keys/'+keyId+'/revoke',{method:'POST'});
  const d=await r.json();
  if(!d.success){alert(d.detail||'تعذّر الإبطال');return;}
  loadApiKeys();
}

async function resetManagerPass(){
  const cid=document.getElementById('detail-cid').value;
  const pass=document.getElementById('mgr-pass').value.trim();
  const msg=document.getElementById('mgr-msg');
  if(!pass){msg.textContent='أدخل كلمة المرور الجديدة';msg.style.color='#dc2626';msg.style.display='block';return;}
  const r=await fetch('/api/admin/clients/'+cid+'/reset-password',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pass})});
  const d=await r.json();
  if(d.success){msg.textContent='✓ تم تغيير كلمة المرور بنجاح';msg.style.color='#16a34a';}
  else{msg.textContent=d.error||'خطأ';msg.style.color='#dc2626';}
  msg.style.display='block';
  document.getElementById('mgr-pass').value='';
}

// ─── Modules ────────────────────────────────────────────────
const ALL_MODULES=[
  {id:'M01',name:'الاستقبال'},{id:'M02',name:'النزلاء'},{id:'M03',name:'الفواتير'},
  {id:'M04',name:'نقطة البيع'},{id:'M05',name:'الإشراف الداخلي'},{id:'M06',name:'المستودع'},
  {id:'M07',name:'الصيانة'},{id:'M08',name:'واتساب'},{id:'M09',name:'الحجوزات'},
  {id:'M10',name:'التسويق'},{id:'M11',name:'إدارة القنوات'},{id:'M12',name:'الذكاء الاصطناعي'},
  {id:'M13',name:'التقارير'},{id:'M14',name:'الموظفون'},{id:'M15',name:'السياحة'},
  {id:'M16',name:'المفاتيح الإلكترونية'},{id:'M17',name:'الحجوزات الخارجية'},
];
const PLAN_MODULES={
  trial:['M01','M02'],
  starter:['M01','M02','M07'],
  operations:['M01','M02','M05','M07','M08','M13'],
  professional:['M01','M02','M03','M04','M05','M06','M07','M08','M11','M13'],
  enterprise:ALL_MODULES.map(m=>m.id)
};

function initModulesPane(){
  const sel=document.getElementById('mod-client-sel');
  if(sel.options.length<=1){
    _clients.forEach(c=>{const o=document.createElement('option');o.value=c.id;o.textContent=(c.name||c.id)+' ('+c.plan+')';sel.appendChild(o);});
  }
}

function loadModules(){
  const cid=document.getElementById('mod-client-sel').value;
  const grid=document.getElementById('modules-grid');
  if(!cid){grid.innerHTML='';document.getElementById('modules-save-row').style.display='none';return;}
  const c=_clients.find(x=>x.id===cid)||{plan:'trial'};
  const enabledByPlan=PLAN_MODULES[c.plan]||[];
  const customEnabled=c.enabled_modules||enabledByPlan;
  grid.innerHTML=ALL_MODULES.map(m=>{
    const checked=customEnabled.includes(m.id);
    const byPlan=enabledByPlan.includes(m.id);
    return `<label style="display:flex;align-items:center;gap:8px;background:${checked?'#f0fdf4':'#f8fafc'};border:1.5px solid ${checked?'#86efac':'#e2e8f0'};border-radius:10px;padding:12px 14px;cursor:pointer;transition:.2s">
      <input type="checkbox" value="${m.id}" ${checked?'checked':''} onchange="onModuleToggle()" style="width:16px;height:16px;accent-color:#10B981">
      <div>
        <div style="font-weight:600;font-size:.82rem;color:#0F2640">${m.id}</div>
        <div style="font-size:.75rem;color:#64748b">${m.name}</div>
        ${byPlan?'<span style="font-size:.65rem;color:#059669">✓ مشمول في الخطة</span>':''}
      </div>
    </label>`;
  }).join('');
  document.getElementById('modules-save-row').style.display='block';
  document.getElementById('mod-saved').style.display='none';
}

function onModuleToggle(){
  const checkboxes=document.querySelectorAll('#modules-grid input[type=checkbox]');
  checkboxes.forEach(cb=>{
    const lbl=cb.closest('label');
    const on=cb.checked;
    lbl.style.background=on?'#f0fdf4':'#f8fafc';
    lbl.style.borderColor=on?'#86efac':'#e2e8f0';
  });
}

async function saveModules(){
  const cid=document.getElementById('mod-client-sel').value;
  if(!cid)return;
  const enabled=[...document.querySelectorAll('#modules-grid input[type=checkbox]:checked')].map(cb=>cb.value);
  const r=await fetch('/api/admin/clients/'+cid+'/modules',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled_modules:enabled})});
  const d=await r.json();
  if(d.success){
    const saved=document.getElementById('mod-saved');
    saved.style.display='inline';
    setTimeout(()=>saved.style.display='none',3000);
    // update local cache
    const c=_clients.find(x=>x.id===cid);
    if(c)c.enabled_modules=enabled;
  }
}

// ─── Marketers ──────────────────────────────────────────────
function _refLink(code){return location.origin+'/ref/'+code;}

async function loadMarketers(){
  const r=await fetch('/api/admin/marketers').then(r=>r.json()).catch(()=>({}));
  const mkts=r.marketers||[];
  document.getElementById('mktr-body').innerHTML=mkts.map(m=>{
    const link=_refLink(m.ref_code);
    const sc=m.status==='active'?'bg':'br';
    return `<tr>
      <td><strong>${m.name}</strong>${m.phone?`<br><small style="color:#94a3b8">${m.phone}</small>`:''}</td>
      <td><code style="background:#f1f5f9;padding:2px 8px;border-radius:4px;font-size:.8rem">${m.ref_code}</code></td>
      <td>
        <input readonly value="${link}" style="width:200px;font-size:.72rem;padding:4px 8px;border:1px solid #e2e8f0;border-radius:6px;background:#f8fafc">
        <button onclick="copyLink('${link}')" style="background:#185FA5;color:#fff;border:none;padding:4px 8px;border-radius:5px;cursor:pointer;font-size:.72rem;margin-right:4px">نسخ</button>
      </td>
      <td><span style="font-weight:700;color:#185FA5">${m.referral_count||0}</span> تسجيل</td>
      <td>${m.commission_rate||10}%</td>
      <td><span class="badge ${sc}">${m.status==='active'?'نشط':'موقوف'}</span></td>
      <td style="white-space:nowrap">
        <button class="btn btn-p" onclick="viewRefs(${m.id},'${m.name}','${m.ref_code}')" style="margin-left:4px">&#128065; عرض</button>
        <button class="btn btn-r" onclick="deactivateMktr(${m.id})">تعطيل</button>
      </td>
    </tr>`;
  }).join('')||'<tr><td colspan="7" style="text-align:center;color:#94a3b8;padding:32px">لا يوجد مسوقون</td></tr>';
}

function copyLink(link){navigator.clipboard.writeText(link).catch(()=>{});const el=document.getElementById('mktr-link-info');el.style.display='block';el.textContent='✓ تم نسخ الرابط: '+link;setTimeout(()=>el.style.display='none',4000);}

function openAddMktr(){['mk-name','mk-code','mk-email','mk-phone','mk-notes'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});document.getElementById('mk-comm').value='10';document.getElementById('mk-err').style.display='none';openModal('modal-mktr');}

async function addMarketer(){
  const name=document.getElementById('mk-name').value.trim();
  const err=document.getElementById('mk-err');
  if(!name){err.textContent='الاسم مطلوب';err.style.display='block';return;}
  const body={name,phone:document.getElementById('mk-phone').value,email:document.getElementById('mk-email').value,ref_code:document.getElementById('mk-code').value.trim().toUpperCase()||'',commission_rate:parseFloat(document.getElementById('mk-comm').value)||10,notes:document.getElementById('mk-notes').value};
  const r=await fetch('/api/admin/marketers',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const d=await r.json();
  if(d.success){closeModal('modal-mktr');loadMarketers();const link=_refLink(d.marketer.ref_code);const el=document.getElementById('mktr-link-info');el.style.display='block';el.textContent='✓ أُضيف المسوق — الرابط: '+link;}
  else{err.textContent=d.error||'خطأ';err.style.display='block';}
}

async function deactivateMktr(id){if(!confirm('تعطيل هذا المسوق؟'))return;await fetch('/api/admin/marketers/'+id,{method:'DELETE'});loadMarketers();}

async function viewRefs(id,name,code){
  document.getElementById('refs-title').textContent='تسجيلات: '+name;
  document.getElementById('refs-link').textContent='رابط الإحالة: '+_refLink(code);
  openModal('modal-refs');
  const r=await fetch('/api/admin/marketers/'+id+'/referrals').then(r=>r.json()).catch(()=>({}));
  const refs=r.referrals||[];
  document.getElementById('refs-body').innerHTML=refs.length?refs.map(ref=>`<tr>
    <td><strong>${ref.client_name||ref.client_id}</strong></td>
    <td><span class="badge bb">${PLANS[ref.plan]||ref.plan||'trial'}</span></td>
    <td>${(ref.converted_at||'').substring(0,10)}</td>
  </tr>`).join(''):'<tr><td colspan="3" style="text-align:center;color:#94a3b8;padding:24px">لا توجد تسجيلات بعد</td></tr>';
}

// Auto-refresh overview every 30s
setInterval(loadOverview,30000);
loadOverview();
</script>
</body>
</html>"""


def _client_dashboard(client: dict) -> str:
    name = client.get("name", client.get("hotel_name", client.get("id", "المنشأة")))
    plan = client.get("plan", "starter")

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ضيوف — {name}</title>
{_NAV}
<style>
  .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px}}
  .kpi-card{{background:#fff;border-radius:12px;padding:20px 22px;box-shadow:0 1px 4px rgba(0,0,0,.06);border-top:3px solid #185FA5}}
  .kpi-card.green{{border-top-color:#10B981}}.kpi-card.gold{{border-top-color:#F59E0B}}.kpi-card.purple{{border-top-color:#8b5cf6}}
  .kpi-card .val{{font-size:1.9rem;font-weight:700;color:#0F2640;margin-bottom:4px}}
  .kpi-card .lbl{{font-size:.8rem;color:#64748b}}
  .section{{background:#fff;border-radius:12px;padding:22px 24px;box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:20px}}
  .section-hdr{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #f1f5f9}}
  .section-hdr h3{{font-size:.95rem;font-weight:600;color:#0F2640}}
  .modal-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:1000;align-items:center;justify-content:center}}
  .modal-overlay.open{{display:flex}}
  .modal{{background:#fff;border-radius:14px;padding:28px;width:100%;max-width:500px;box-shadow:0 20px 60px rgba(0,0,0,.2);max-height:90vh;overflow-y:auto}}
  .modal h4{{margin-bottom:20px;color:#0F2640;font-size:1rem;font-weight:600}}
  .form-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  .modal-actions{{display:flex;gap:10px;justify-content:flex-end;margin-top:20px;padding-top:16px;border-top:1px solid #f1f5f9}}
  .empty{{text-align:center;padding:32px;color:#94a3b8;font-size:.875rem}}
  .notif-item{{background:#f8fafc;border-radius:8px;padding:12px 14px;border-right:3px solid #185FA5;margin-bottom:8px}}
  .notif-item.warn{{border-right-color:#F59E0B}}
  .ai-box{{background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:16px;margin-top:16px;white-space:pre-wrap;font-size:.875rem;color:#0369a1;min-height:60px}}
  .channel-card{{background:#f8fafc;border-radius:10px;padding:18px;margin-bottom:14px;border:1.5px solid #e2e8f0}}
  .channel-card h4{{font-size:.9rem;font-weight:600;color:#0F2640;margin-bottom:12px}}
  .pane-section{{display:none}}.pane-section.active{{display:block}}
</style>
</head>
<body>
<div class="sidebar">
  <div class="logo"><h1>ضيوف</h1><small id="s-hotel-name">{name}</small></div>
  <a href="#" class="active" onclick="showSection('home')"><span class="icon">&#128200;</span> الرئيسية</a>
  <a href="#" onclick="showSection('guests')"><span class="icon">&#128101;</span> النزلاء</a>
  <a href="#" onclick="showSection('bookings')"><span class="icon">&#128197;</span> الحجوزات</a>
  <a href="#" onclick="showSection('invoices')"><span class="icon">&#128203;</span> الفواتير</a>
  <a href="#" onclick="showSection('pos')"><span class="icon">&#128184;</span> نقطة البيع</a>
  <a href="#" onclick="showSection('reports')"><span class="icon">&#128202;</span> التقارير</a>
  <a href="#" onclick="showSection('channels')"><span class="icon">&#127760;</span> القنوات</a>
  <a href="#" onclick="showSection('ai')"><span class="icon">&#129504;</span> الرؤى الذكية</a>
  <a href="#" onclick="showSection('support')"><span class="icon">&#127917;</span> الدعم</a>
  <a href="#" onclick="showSection('settings')"><span class="icon">&#9881;</span> الإعدادات</a>
  <a href="/api/logout" style="color:#ef4444;margin-top:auto"><span class="icon">&#128682;</span> خروج</a>
</div>
<div class="main">
  <div class="topbar">
    <h2 id="page-title">لوحة التحكم</h2>
    <div style="display:flex;align-items:center;gap:12px">
      <span id="sub-badge" class="badge badge-blue">{plan}</span>
      <a href="/api/logout" class="btn btn-danger" style="padding:8px 14px">خروج</a>
    </div>
  </div>

  <!-- HOME -->
  <div id="sec-home" class="pane-section active">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="val" id="kpi-active">-</div><div class="lbl">حجوزات نشطة</div></div>
      <div class="kpi-card green"><div class="val" id="kpi-guests">-</div><div class="lbl">إجمالي النزلاء</div></div>
      <div class="kpi-card gold"><div class="val" id="kpi-revenue">-</div><div class="lbl">إيرادات هذا الشهر (ر.س)</div></div>
      <div class="kpi-card purple"><div class="val" id="kpi-monthly">-</div><div class="lbl">حجوزات هذا الشهر</div></div>
    </div>
    <div class="section">
      <div class="section-hdr"><h3>آخر الحجوزات</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="showSection('bookings')">عرض الكل</button></div>
      <div style="overflow-x:auto"><table id="tbl-home-bk">
        <thead><tr><th>النزيل</th><th>الغرفة</th><th>الوصول</th><th>المغادرة</th><th>الحالة</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">جارٍ التحميل...</td></tr></tbody>
      </table></div>
    </div>
    <div class="section">
      <div class="section-hdr"><h3>الإشعارات</h3></div>
      <div id="notif-list"><div class="empty">لا توجد إشعارات</div></div>
    </div>
  </div>

  <!-- GUESTS -->
  <div id="sec-guests" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>النزلاء</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-guest')">+ نزيل جديد</button></div>
      <div style="overflow-x:auto"><table id="tbl-guests">
        <thead><tr><th>الاسم</th><th>رقم الهوية</th><th>الجنسية</th><th>الهاتف</th><th>الحالة</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">لا يوجد نزلاء</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- BOOKINGS -->
  <div id="sec-bookings" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>الحجوزات</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-booking')">+ حجز جديد</button></div>
      <div style="overflow-x:auto"><table id="tbl-bookings">
        <thead><tr><th>رقم الحجز</th><th>النزيل</th><th>الوصول</th><th>المغادرة</th><th>المبلغ</th><th>الحالة</th></tr></thead>
        <tbody><tr><td colspan="6" class="empty">لا توجد حجوزات</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- INVOICES -->
  <div id="sec-invoices" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>الفواتير</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-invoice')">+ فاتورة جديدة</button></div>
      <div style="overflow-x:auto"><table id="tbl-invoices">
        <thead><tr><th>رقم الفاتورة</th><th>التاريخ</th><th>المبلغ</th><th>الحالة</th><th>إجراء</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">لا توجد فواتير</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- POS -->
  <div id="sec-pos" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>نقطة البيع</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-pos')">+ معاملة جديدة</button></div>
      <div style="overflow-x:auto"><table id="tbl-pos">
        <thead><tr><th>التاريخ</th><th>الفئة</th><th>الوصف</th><th>المبلغ</th><th>الدفع</th></tr></thead>
        <tbody><tr><td colspan="5" class="empty">لا توجد معاملات</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- REPORTS -->
  <div id="sec-reports" class="pane-section">
    <div class="kpi-grid">
      <div class="kpi-card"><div class="val" id="rep-bk">-</div><div class="lbl">إجمالي الحجوزات</div></div>
      <div class="kpi-card green"><div class="val" id="rep-rev">-</div><div class="lbl">إجمالي الإيرادات (ر.س)</div></div>
    </div>
    <div class="section">
      <div class="section-hdr"><h3>الإيرادات الشهرية</h3></div>
      <div style="overflow-x:auto"><table id="tbl-monthly">
        <thead><tr><th>الشهر</th><th>الإيرادات (ر.س)</th></tr></thead>
        <tbody></tbody>
      </table></div>
    </div>
  </div>

  <!-- CHANNELS -->
  <div id="sec-channels" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>إدارة القنوات</h3></div>
      <div class="channel-card">
        <h4>&#127760; Booking.com</h4>
        <div class="form-row">
          <div class="form-group"><label>Hotel ID</label><input id="bc-hotel" placeholder="12345678"></div>
          <div class="form-group"><label>API Key</label><input id="bc-key" type="password" placeholder="••••••••"></div>
        </div>
        <button class="btn btn-primary" style="padding:8px 18px;font-size:13px;width:auto" onclick="saveBC()">حفظ</button>
      </div>
      <div class="channel-card">
        <h4>&#127966; مواسم</h4>
        <div class="form-row">
          <div class="form-group"><label>Hotel ID</label><input id="mw-hotel" placeholder="HOTEL_ID"></div>
          <div class="form-group"><label>iCal URL</label><input id="mw-ical" placeholder="https://..."></div>
        </div>
        <button class="btn btn-primary" style="padding:8px 18px;font-size:13px;width:auto" onclick="saveMawasim()">حفظ</button>
      </div>
    </div>
  </div>

  <!-- AI -->
  <div id="sec-ai" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>الرؤى الذكية بالذكاء الاصطناعي</h3></div>
      <div class="form-group"><label>اسألني عن بيانات فندقك</label>
        <textarea id="ai-prompt" rows="3" style="width:100%;padding:10px;border:1.5px solid #d1d5db;border-radius:8px;font-family:inherit;font-size:.9rem;resize:vertical" placeholder="مثال: ما هي أكثر الغرف حجزاً هذا الشهر؟ أو قدّم تحليلاً للإيرادات"></textarea>
      </div>
      <button class="btn btn-primary" style="width:auto;padding:10px 24px" onclick="analyzeAI()">تحليل</button>
      <div class="ai-box" id="ai-result" style="display:none"></div>
    </div>
  </div>

  <!-- SUPPORT -->
  <div id="sec-support" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>تذاكر الدعم</h3><button class="btn btn-primary" style="padding:6px 14px;font-size:13px" onclick="openModal('m-ticket')">+ تذكرة جديدة</button></div>
      <div style="overflow-x:auto"><table id="tbl-tickets">
        <thead><tr><th>الموضوع</th><th>الحالة</th><th>التاريخ</th></tr></thead>
        <tbody><tr><td colspan="3" class="empty">لا توجد تذاكر</td></tr></tbody>
      </table></div>
    </div>
  </div>

  <!-- SETTINGS -->
  <div id="sec-settings" class="pane-section">
    <div class="section">
      <div class="section-hdr"><h3>إعدادات المنشأة</h3></div>
      <div class="form-row">
        <div class="form-group"><label>اسم المنشأة</label><input id="set-name" placeholder="فندق الواحة"></div>
        <div class="form-group"><label>المدينة</label><input id="set-city" placeholder="الرياض"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>رقم الهاتف</label><input id="set-phone" placeholder="+966xxxxxxxx"></div>
        <div class="form-group"><label>البريد الإلكتروني</label><input id="set-email"></div>
      </div>
      <div class="form-row">
        <div class="form-group"><label>عدد الغرف/الوحدات</label><input type="number" id="set-units"></div>
        <div class="form-group"><label>نوع المنشأة</label>
          <select id="set-type"><option value="hotel">فندق</option><option value="apartment">شقق مخدومة</option><option value="resort">منتجع</option><option value="hostel">استراحة</option></select>
        </div>
      </div>
      <button class="btn btn-primary" style="width:auto;padding:10px 24px" onclick="saveSettings()">حفظ الإعدادات</button>
    </div>
  </div>

</div><!-- end .main -->

<!-- MODALS -->
<div class="modal-overlay" id="m-guest">
  <div class="modal">
    <h4>إضافة نزيل جديد</h4>
    <div class="form-group"><label>الاسم الكامل</label><input id="g-name" placeholder="أحمد محمد العلي"></div>
    <div class="form-row">
      <div class="form-group"><label>نوع الهوية</label><select id="g-id-type"><option value="national_id">هوية وطنية</option><option value="passport">جواز سفر</option><option value="iqama">إقامة</option></select></div>
      <div class="form-group"><label>رقم الهوية</label><input id="g-id-num" placeholder="1xxxxxxxxx"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>الجنسية</label><input id="g-nat" placeholder="سعودي"></div>
      <div class="form-group"><label>رقم الهاتف</label><input id="g-phone" placeholder="+9665xxxxxxxx"></div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-guest')">إلغاء</button>
      <button class="btn btn-primary" onclick="addGuest()">إضافة</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-booking">
  <div class="modal">
    <h4>إضافة حجز جديد</h4>
    <div class="form-row">
      <div class="form-group"><label>تاريخ الوصول</label><input type="date" id="b-in"></div>
      <div class="form-group"><label>تاريخ المغادرة</label><input type="date" id="b-out"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>رقم الغرفة</label><input id="b-room" placeholder="101"></div>
      <div class="form-group"><label>السعر الليلي (ر.س)</label><input type="number" id="b-rate" value="300"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>المصدر</label><select id="b-src"><option value="reception">الاستقبال</option><option value="booking_com">Booking.com</option><option value="mawasim">مواسم</option><option value="phone">هاتف</option></select></div>
      <div class="form-group"><label>الحالة</label><select id="b-status"><option value="confirmed">مؤكد</option><option value="checked_in">داخل</option><option value="checked_out">مغادر</option><option value="cancelled">ملغي</option></select></div>
    </div>
    <div class="form-group"><label>ملاحظات</label><textarea id="b-notes" rows="2" style="width:100%;padding:9px;border:1.5px solid #d1d5db;border-radius:7px;font-family:inherit;resize:vertical"></textarea></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-booking')">إلغاء</button>
      <button class="btn btn-primary" onclick="addBooking()">إضافة</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-invoice">
  <div class="modal">
    <h4>إنشاء فاتورة جديدة</h4>
    <div class="form-row">
      <div class="form-group"><label>رقم الحجز</label><input id="inv-bk" placeholder="BK-001"></div>
      <div class="form-group"><label>المبلغ الإجمالي (ر.س)</label><input type="number" id="inv-total" value="0"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>ضريبة ق.م (ر.س)</label><input type="number" id="inv-vat" value="0"></div>
      <div class="form-group"><label>طريقة الدفع</label><select id="inv-pay"><option value="cash">نقد</option><option value="card">بطاقة</option><option value="transfer">تحويل</option></select></div>
    </div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-invoice')">إلغاء</button>
      <button class="btn btn-primary" onclick="addInvoice()">إنشاء</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-pos">
  <div class="modal">
    <h4>معاملة نقطة البيع</h4>
    <div class="form-row">
      <div class="form-group"><label>الفئة</label><select id="pos-cat"><option value="restaurant">مطعم</option><option value="laundry">غسيل</option><option value="minibar">ميني بار</option><option value="parking">موقف</option><option value="other">أخرى</option></select></div>
      <div class="form-group"><label>المبلغ (ر.س)</label><input type="number" id="pos-amt" value="0"></div>
    </div>
    <div class="form-row">
      <div class="form-group"><label>طريقة الدفع</label><select id="pos-pay"><option value="cash">نقد</option><option value="card">بطاقة</option></select></div>
      <div class="form-group"><label>ضريبة ق.م (ر.س)</label><input type="number" id="pos-vat" value="0"></div>
    </div>
    <div class="form-group"><label>وصف</label><input id="pos-desc" placeholder="وصف المعاملة"></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-pos')">إلغاء</button>
      <button class="btn btn-primary" onclick="addPOS()">تسجيل</button>
    </div>
  </div>
</div>

<div class="modal-overlay" id="m-ticket">
  <div class="modal">
    <h4>فتح تذكرة دعم</h4>
    <div class="form-group"><label>الموضوع</label><input id="tk-subj" placeholder="موضوع التذكرة"></div>
    <div class="form-group"><label>الرسالة</label><textarea id="tk-body" rows="4" style="width:100%;padding:9px;border:1.5px solid #d1d5db;border-radius:7px;font-family:inherit;resize:vertical" placeholder="اشرح مشكلتك..."></textarea></div>
    <div class="modal-actions">
      <button class="btn btn-outline" onclick="closeModal('m-ticket')">إلغاء</button>
      <button class="btn btn-primary" onclick="openTicket()">إرسال</button>
    </div>
  </div>
</div>

<script>
const SEC_TITLES={{'home':'لوحة التحكم','guests':'النزلاء','bookings':'الحجوزات','invoices':'الفواتير','pos':'نقطة البيع','reports':'التقارير','channels':'القنوات','ai':'الرؤى الذكية','support':'الدعم','settings':'الإعدادات'}};

function showSection(s){{
  document.querySelectorAll('.pane-section').forEach(el=>el.classList.remove('active'));
  document.querySelectorAll('.sidebar a').forEach(el=>el.classList.remove('active'));
  document.getElementById('sec-'+s).classList.add('active');
  const links=document.querySelectorAll('.sidebar a');
  const idx={{'home':0,'guests':1,'bookings':2,'invoices':3,'pos':4,'reports':5,'channels':6,'ai':7,'support':8,'settings':9}};
  if(links[idx[s]])links[idx[s]].classList.add('active');
  document.getElementById('page-title').textContent=SEC_TITLES[s]||s;
  const loaders={{'home':loadHome,'guests':loadGuests,'bookings':loadBookings,'invoices':loadInvoices,'pos':loadPOS,'reports':loadReports,'support':loadSupport,'settings':loadSettings}};
  if(loaders[s])loaders[s]();
  return false;
}}

function openModal(id){{document.getElementById(id).classList.add('open')}}
function closeModal(id){{document.getElementById(id).classList.remove('open')}}

function badge(s){{
  const m={{'confirmed':'badge-blue','checked_in':'badge-green','checked_out':'','cancelled':'badge-red','pending':'badge-yellow','paid':'badge-green','unpaid':'badge-yellow','open':'badge-yellow','closed':'badge-green','trial':'badge-yellow','active':'badge-green','suspended':'badge-red'}};
  const ar={{'confirmed':'مؤكد','checked_in':'داخل','checked_out':'مغادر','cancelled':'ملغي','pending':'معلق','paid':'مدفوع','unpaid':'غير مدفوع','open':'مفتوح','closed':'مغلق','trial':'تجريبي','active':'نشط','suspended':'موقوف'}};
  return `<span class="badge ${{m[s]||''}}">${{ar[s]||s}}</span>`;
}}

async function loadHome(){{
  const r=await fetch('/api/kpi');const d=await r.json();
  if(d.kpi||d.data){{
    const k=d.kpi||d.data;
    document.getElementById('kpi-active').textContent=k.active_bookings||0;
    document.getElementById('kpi-guests').textContent=k.total_guests||0;
    document.getElementById('kpi-revenue').textContent=(k.monthly_revenue||0).toLocaleString('ar-SA');
    document.getElementById('kpi-monthly').textContent=k.monthly_bookings||0;
  }}
  const br=await fetch('/api/bookings');const bd=await br.json();
  const tb=document.querySelector('#tbl-home-bk tbody');tb.innerHTML='';
  (bd.data||[]).slice(0,5).forEach(b=>{{
    tb.innerHTML+=`<tr><td>${{b.guest_id||b.guest_name||'—'}}</td><td>${{b.room_id||b.room_number||'—'}}</td><td>${{b.check_in||''}}</td><td>${{b.check_out||''}}</td><td>${{badge(b.status||'confirmed')}}</td></tr>`;
  }});
  if(!(bd.data||[]).length)tb.innerHTML='<tr><td colspan="5" class="empty">لا توجد حجوزات</td></tr>';
  const nr=await fetch('/api/notifications');const nd=await nr.json();
  const nl=document.getElementById('notif-list');nl.innerHTML='';
  if(!(nd.notifications||[]).length){{nl.innerHTML='<div class="empty">لا توجد إشعارات</div>';return;}}
  nd.notifications.forEach(n=>{{nl.innerHTML+=`<div class="notif-item ${{n.type==='warn'?'warn':''}}"><strong>${{n.title||''}}</strong><br><small>${{n.body||''}}</small></div>`;}});
}}

async function loadGuests(){{
  const r=await fetch('/api/guests');const d=await r.json();
  const tb=document.querySelector('#tbl-guests tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="5" class="empty">لا يوجد نزلاء</td></tr>';return;}}
  d.data.forEach(g=>{{
    tb.innerHTML+=`<tr><td>${{g.full_name||g.name||''}}</td><td>${{g.id_number||''}}</td><td>${{g.nationality||''}}</td><td>${{g.absher_phone||g.phone||''}}</td><td>${{badge(g.data_status||'incomplete')}}</td></tr>`;
  }});
}}

async function addGuest(){{
  const body={{full_name:document.getElementById('g-name').value,id_type:document.getElementById('g-id-type').value,id_number:document.getElementById('g-id-num').value,nationality:document.getElementById('g-nat').value,absher_phone:document.getElementById('g-phone').value,data_status:'complete'}};
  await fetch('/api/guests',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-guest');loadGuests();
}}

async function loadBookings(){{
  const r=await fetch('/api/bookings');const d=await r.json();
  const tb=document.querySelector('#tbl-bookings tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="6" class="empty">لا توجد حجوزات</td></tr>';return;}}
  d.data.forEach(b=>{{
    tb.innerHTML+=`<tr><td>${{b.id||''}}</td><td>${{b.guest_id||b.guest_name||''}}</td><td>${{b.check_in||''}}</td><td>${{b.check_out||''}}</td><td>${{(b.total_room||b.total_amount||0).toLocaleString('ar-SA')}} ر.س</td><td>${{badge(b.status||'confirmed')}}</td></tr>`;
  }});
}}

async function addBooking(){{
  const cin=document.getElementById('b-in').value;const cout=document.getElementById('b-out').value;
  const rate=parseFloat(document.getElementById('b-rate').value)||0;
  let nights=0;try{{nights=Math.max(0,(new Date(cout)-new Date(cin))/86400000);}}catch(e){{}}
  const body={{check_in:cin,check_out:cout,room_id:document.getElementById('b-room').value,nightly_rate:rate,total_room:rate*nights,source:document.getElementById('b-src').value,status:document.getElementById('b-status').value,notes:document.getElementById('b-notes').value}};
  await fetch('/api/bookings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-booking');loadBookings();
}}

async function loadInvoices(){{
  const r=await fetch('/api/invoices');const d=await r.json();
  const tb=document.querySelector('#tbl-invoices tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="5" class="empty">لا توجد فواتير</td></tr>';return;}}
  d.data.forEach(inv=>{{
    const iid=inv.id||inv.invoice_number||'';
    tb.innerHTML+=`<tr><td>${{iid}}</td><td>${{(inv.issue_date||inv.created_at||'').substring(0,10)}}</td><td>${{(inv.total_amount||inv.total||0).toLocaleString('ar-SA')}} ر.س</td><td>${{badge(inv.payment_status||'paid')}}</td>
    <td><button onclick="payInv('${{iid}}')" style="background:#dcfce7;color:#16a34a;border:none;padding:4px 10px;border-radius:5px;cursor:pointer;font-size:12px">دفع</button></td></tr>`;
  }});
}}

async function addInvoice(){{
  const body={{booking_id:document.getElementById('inv-bk').value,total_amount:parseFloat(document.getElementById('inv-total').value)||0,vat_amount:parseFloat(document.getElementById('inv-vat').value)||0,payment_method:document.getElementById('inv-pay').value,payment_status:'pending',issue_date:new Date().toISOString().substring(0,10)}};
  body.subtotal=body.total_amount-body.vat_amount;
  await fetch('/api/invoices',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-invoice');loadInvoices();
}}

async function payInv(id){{
  await fetch('/api/invoices/'+id+'/pay',{{method:'POST'}});loadInvoices();
}}

async function loadPOS(){{
  const r=await fetch('/api/pos');const d=await r.json();
  const tb=document.querySelector('#tbl-pos tbody');tb.innerHTML='';
  if(!(d.data||[]).length){{tb.innerHTML='<tr><td colspan="5" class="empty">لا توجد معاملات</td></tr>';return;}}
  d.data.forEach(tx=>{{
    tb.innerHTML+=`<tr><td>${{tx.date||''}}</td><td>${{tx.category||''}}</td><td>${{tx.description||''}}</td><td>${{(tx.amount||0).toLocaleString('ar-SA')}} ر.س</td><td>${{tx.payment_method||''}}</td></tr>`;
  }});
}}

async function addPOS(){{
  const amt=parseFloat(document.getElementById('pos-amt').value)||0;
  const vat=parseFloat(document.getElementById('pos-vat').value)||0;
  const body={{category:document.getElementById('pos-cat').value,amount:amt,vat_amount:vat,net_amount:amt-vat,payment_method:document.getElementById('pos-pay').value,description:document.getElementById('pos-desc').value,date:new Date().toISOString().substring(0,10)}};
  await fetch('/api/pos',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  closeModal('m-pos');loadPOS();
}}

async function loadReports(){{
  const r=await fetch('/api/analytics');const d=await r.json();
  const data=d.data||{{}};
  document.getElementById('rep-bk').textContent=data.total_bookings||0;
  document.getElementById('rep-rev').textContent=(data.total_revenue||0).toLocaleString('ar-SA');
  const tb=document.querySelector('#tbl-monthly tbody');tb.innerHTML='';
  (data.monthly_revenue||[]).forEach(m=>{{
    tb.innerHTML+=`<tr><td>${{m.month||''}}</td><td>${{(m.revenue||0).toLocaleString('ar-SA')}}</td></tr>`;
  }});
}}

async function loadSupport(){{
  const r=await fetch('/api/tickets');const d=await r.json();
  const tb=document.querySelector('#tbl-tickets tbody');tb.innerHTML='';
  if(!(d.tickets||[]).length){{tb.innerHTML='<tr><td colspan="3" class="empty">لا توجد تذاكر</td></tr>';return;}}
  d.tickets.forEach(t=>{{
    tb.innerHTML+=`<tr><td>${{t.subject||''}}</td><td>${{badge(t.status||'open')}}</td><td>${{(t.created_at||'').substring(0,10)}}</td></tr>`;
  }});
}}

async function openTicket(){{
  const subject=document.getElementById('tk-subj').value;
  const body=document.getElementById('tk-body').value;
  if(!subject||!body)return;
  await fetch('/api/tickets',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{subject,body}})}});
  closeModal('m-ticket');loadSupport();
}}

async function loadSettings(){{
  const r=await fetch('/api/settings');const d=await r.json();
  const c=d.data||d.client||{{}};
  document.getElementById('set-name').value=c.name||c.hotel_name||'';
  document.getElementById('set-city').value=c.city||'';
  document.getElementById('set-phone').value=c.phone||'';
  document.getElementById('set-email').value=c.email||'';
  document.getElementById('set-units').value=c.units_count||0;
  document.getElementById('set-type').value=c.type||'hotel';
}}

async function saveSettings(){{
  const body={{name:document.getElementById('set-name').value,city:document.getElementById('set-city').value,phone:document.getElementById('set-phone').value,email:document.getElementById('set-email').value,units_count:parseInt(document.getElementById('set-units').value)||0,type:document.getElementById('set-type').value}};
  await fetch('/api/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});
  alert('تم حفظ الإعدادات');
}}

async function analyzeAI(){{
  const prompt=document.getElementById('ai-prompt').value;
  if(!prompt.trim())return;
  const res=document.getElementById('ai-result');
  res.style.display='block';res.textContent='جاري التحليل...';
  const r=await fetch('/api/ai/analyze',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{prompt,context:{{}}}})}});
  const d=await r.json();
  res.textContent=d.response||d.error||'لا توجد نتيجة';
}}

async function saveBC(){{
  const hotel_id=document.getElementById('bc-hotel').value;
  const api_key=document.getElementById('bc-key').value;
  await fetch('/api/channels/booking-com/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hotel_id,api_key}})}});
  alert('تم حفظ إعدادات Booking.com');
}}

async function saveMawasim(){{
  const hotel_id=document.getElementById('mw-hotel').value;
  const ical_url=document.getElementById('mw-ical').value;
  await fetch('/api/channels/mawasim/settings',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{hotel_id,ical_url}})}});
  alert('تم حفظ إعدادات مواسم');
}}

loadHome();
</script>
</body>
</html>"""
