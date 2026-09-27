/* =========================================================================
   advisor.js — الرؤى الذكية: اسأل عن أرقام منشأتك

   المسار كان مبنيّاً منذ دفعاتٍ بلا شاشةٍ تناديه. هذه هي الشاشة.

   **لا تُرسَل بيانات نزيلٍ.** اللقطة الرقمية تُبنى على الخادم — بناؤها
   هنا يعني أن المتصفّح يختار ما يُرسَل للنموذج، فيستطيع مُعدِّلٌ إرسال
   أسماء النزلاء بتغيير هذا الملف.
   ========================================================================= */
(function () {
  'use strict';

  var busy = false;

  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v == null ? '' : v)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  async function api(path, opts) {
    opts = opts || {};
    try {
      var res = await fetch(path, Object.assign({
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' }
      }, opts));
      var body = null;
      try { body = await res.json(); } catch (e) { /* ردٌّ بلا جسم */ }
      if (!res.ok) {
        return { ok: false, status: res.status,
                 error: (body && (body.detail || body.error)) || ('خطأ ' + res.status) };
      }
      return { ok: true, data: body };
    } catch (e) {
      return { ok: false, status: 0, error: 'تعذّر الاتصال — تحقّق من الشبكة' };
    }
  }

  /* ── الحالة ──────────────────────────────────────────────────── */
  async function loadStatus() {
    var res = await api('/api/insights/status');
    var box = $('ai-state');
    if (!res.ok) {
      // ٤٠٣ يعني موظفاً بلا صلاحية — والرسالة تشرح لا تُبهم
      box.innerHTML = '<div class="ai-off">' + esc(res.error) + '</div>';
      $('ai-form').hidden = true;
      return;
    }
    var d = (res.data && res.data.data) || {};
    if (!d.enabled) {
      box.innerHTML = '<div class="ai-off"><strong>الخدمة غير مُفعَّلة.</strong><br/>' +
        esc(d.note || '') + '</div>';
      $('ai-form').hidden = true;
      return;
    }
    box.innerHTML = '<div class="ai-on">جاهز · ' + esc(d.remaining) +
      ' سؤالاً متبقياً هذه الساعة</div>';
    $('ai-form').hidden = false;
  }

  function setRemaining(n) {
    var box = $('ai-state');
    if (box && n != null) {
      box.innerHTML = '<div class="ai-on">جاهز · ' + esc(n) +
        ' سؤالاً متبقياً هذه الساعة</div>';
    }
  }

  /* ── السؤال ──────────────────────────────────────────────────── */
  async function ask(question) {
    if (busy) return;
    var text = (question || $('ai-q').value || '').trim();
    if (!text) { return; }

    busy = true;
    $('ai-send').disabled = true;
    $('ai-send').textContent = 'يُفكّر…';
    render(text, null, true);

    var res = await api('/api/insights/ask',
      { method: 'POST', body: JSON.stringify({ prompt: text }) });

    busy = false;
    $('ai-send').disabled = false;
    $('ai-send').textContent = 'اسأل';

    if (!res.ok) { render(text, res.error, false, true); return; }
    var d = (res.data && res.data.data) || {};
    render(text, d.answer, false, false, d.truncated);
    setRemaining(d.remaining);
    $('ai-q').value = '';
  }

  /* الجواب يُعرض بفقراتٍ لا نصّاً ملتصقاً — والنصّ مُهرَّب دائماً. */
  function render(question, answer, pending, isError, truncated) {
    var host = $('ai-thread');
    var card = document.createElement('div');
    card.className = 'ai-turn' + (isError ? ' is-err' : '');
    card.innerHTML =
      '<div class="ai-q">' + esc(question) + '</div>' +
      '<div class="ai-a">' +
        (pending ? '<span class="ai-dots">يقرأ أرقامك…</span>'
                 : (answer || '').split(/\n{2,}/).map(function (p) {
                     return '<p>' + esc(p).replace(/\n/g, '<br/>') + '</p>';
                   }).join('')) +
      '</div>' +
      (truncated ? '<div class="ai-trunc">الجواب طويل وقُطع — اسأل عن جزءٍ منه</div>' : '');

    if (pending) {
      card.id = 'ai-pending';
      host.prepend(card);
    } else {
      var old = $('ai-pending');
      if (old) old.replaceWith(card); else host.prepend(card);
    }
  }

  /* ── الأسئلة الجاهزة ─────────────────────────────────────────── */
  function bindSuggestions() {
    document.querySelectorAll('.ai-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        $('ai-q').value = this.textContent.trim();
        ask();
      });
    });
  }

  function bind() {
    $('ai-send').addEventListener('click', function () { ask(); });
    // Ctrl+Enter يُرسل: السؤال قد يكون سطرين، فـEnter وحده يُفسد الكتابة
    $('ai-q').addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter' && (ev.ctrlKey || ev.metaKey)) { ev.preventDefault(); ask(); }
    });
    bindSuggestions();
  }

  function init() {
    bind();
    loadStatus();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
