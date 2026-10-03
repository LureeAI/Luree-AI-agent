from flask import Blueprint, Response
from access_control import csrf_token

chat_ui = Blueprint("chat_ui", __name__)

PAGE = r"""
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="csrf-token" content="{{ csrf_token() }}">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luree AI Agent</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#10121a;color:#eee;
font-family:Arial,sans-serif}
main{max-width:760px;margin:auto;height:100dvh;
display:flex;flex-direction:column;padding:18px}
header{padding:12px 0;border-bottom:1px solid #333;max-height:55dvh;overflow:auto;flex-shrink:0}
h1{font-size:24px;margin:0;color:#eac884}
header p{color:#aaa;font-size:14px}
#messages{flex:1;overflow:auto;padding:18px 0}
.bubble{padding:14px;margin:12px 0;border-radius:16px;
white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.7}
.agent{background:#222633;margin-left:24px}
.user{background:#454035;margin-right:24px}
form{display:flex;gap:10px;padding:12px 0}
textarea{flex:1;background:#222633;color:white;
border:1px solid #555;border-radius:12px;padding:12px;
font:inherit;resize:none}
button{background:#eac884;color:#171717;border:0;
border-radius:12px;padding:12px 18px;font:inherit;cursor:pointer}
button:disabled{opacity:.5}
#status{min-height:24px;color:#bbb;font-size:14px}
.identity{display:flex;align-items:center;gap:16px}
#face{width:150px;height:158px;flex-shrink:0;filter:drop-shadow(0 8px 14px #0008);transition:filter .2s}
#face svg{width:100%;height:100%;overflow:visible}
#face .robot-eyes{transform-box:fill-box;transform-origin:center;animation:robot-blink 6s infinite}
#face .mouth{transform-box:fill-box;transform-origin:center}
#face.speaking .mouth{animation:robot-talk .28s infinite alternate}
#face.thinking .forehead{animation:robot-glow .8s infinite alternate}
#face.listening{filter:drop-shadow(0 0 14px #eac884)}
@keyframes robot-blink{0%,44%,48%,100%{transform:scaleY(1)}46%{transform:scaleY(.12)}}
@keyframes robot-talk{from{transform:scaleY(.45)}to{transform:scaleY(1.4)}}
@keyframes robot-glow{to{opacity:.25}}
@media(max-width:480px){#face{width:120px;height:128px}h1{font-size:21px}}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.controls button{padding:8px 12px;font-size:14px}
@media(prefers-reduced-motion:reduce){#face .robot-eyes,#face .mouth,#face .forehead{animation:none!important}}
</style>
</head>
<body>
<main>
<header>
<div class="identity"><div id="face" role="img" aria-label="رأس روبوت أبيض وذهبي">
<svg viewBox="0 0 180 190" aria-hidden="true">
<defs>
<linearGradient id="ceramic" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fffef9"/><stop offset=".5" stop-color="#f1eadb"/><stop offset="1" stop-color="#c9bc9f"/></linearGradient>
<linearGradient id="gold"><stop stop-color="#99702d"/><stop offset=".45" stop-color="#ffe9a6"/><stop offset="1" stop-color="#b2853c"/></linearGradient>
<radialGradient id="iris"><stop stop-color="#ffedb1"/><stop offset=".65" stop-color="#b58330"/><stop offset="1" stop-color="#503514"/></radialGradient>
</defs>
<rect x="60" y="157" width="60" height="23" rx="9" fill="url(#gold)"/>
<ellipse cx="90" cy="178" rx="38" ry="7" fill="#ede3cd" stroke="#bc944d" stroke-width="3"/>
<rect x="9" y="0" width="20" height="65" rx="10" fill="url(#gold)" transform="translate(0 58)"/>
<rect x="151" y="58" width="20" height="65" rx="10" fill="url(#gold)"/>
<path d="M90 10 C137 10 157 40 155 91 C153 131 133 161 90 166 C47 161 27 131 25 91 C23 40 43 10 90 10Z" fill="url(#ceramic)" stroke="#d5ae64" stroke-width="3"/>
<path d="M49 21 L59 61 M131 21 L121 61" fill="none" stroke="url(#gold)" stroke-width="5"/>
<rect x="81" y="24" width="18" height="27" rx="9" fill="url(#gold)"/>
<rect class="forehead" x="87" y="29" width="6" height="16" rx="3" fill="#fff7d8"/>
<path d="M42 70 Q57 60 70 68 M110 68 Q123 60 138 70" fill="none" stroke="#89652f" stroke-width="4" stroke-linecap="round"/>
<g class="robot-eyes">
<ellipse cx="58" cy="91" rx="20" ry="22" fill="#fff" stroke="#b58b48" stroke-width="2"/>
<ellipse cx="122" cy="91" rx="20" ry="22" fill="#fff" stroke="#b58b48" stroke-width="2"/>
<circle cx="58" cy="92" r="15" fill="url(#iris)"/><circle cx="122" cy="92" r="15" fill="url(#iris)"/>
<circle cx="58" cy="93" r="8" fill="#251b13"/><circle cx="122" cy="93" r="8" fill="#251b13"/>
<circle cx="53" cy="86" r="5" fill="#fff"/><circle cx="117" cy="86" r="5" fill="#fff"/>
</g>
<path d="M85 112 Q90 119 95 112" fill="none" stroke="#c0ab82" stroke-width="2" stroke-linecap="round"/>
<ellipse cx="46" cy="117" rx="10" ry="5" fill="#eac6aa" opacity=".5"/><ellipse cx="134" cy="117" rx="10" ry="5" fill="#eac6aa" opacity=".5"/>
<g class="mouth"><path d="M69 134 Q90 143 111 134 Q105 154 90 154 Q75 154 69 134Z" fill="#463023" stroke="#ac8050" stroke-width="2"/><path d="M73 137 Q90 144 107 137" fill="none" stroke="#fffaf1" stroke-width="4" stroke-linecap="round"/></g>
<path d="M33 116 L45 139 M147 116 L135 139" stroke="url(#gold)" stroke-width="3" fill="none"/>
</svg></div><div><h1>Luree AI Agent</h1><p>مساعدك لإدارة وتحليل متجر Luree Fashions</p></div></div>
<div class="controls"><button id="mic" type="button">🎤 إملاء رسالة</button><button id="voice" type="button" aria-pressed="false">الصوت: متوقف</button><button id="replay" type="button" disabled>قراءة آخر رد</button><button id="stop" type="button">إيقاف الصوت</button></div>
<div class="controls"><button id="logout" type="button">تسجيل خروج</button></div>
<details><summary>تعليماتي المحفوظة</summary><p>اكتبي قواعد المتجر وتفضيلاتك ليستخدمها الوكيل في كل محادثة.</p><textarea id="preferences" maxlength="4000" rows="3" aria-label="تعليمات محفوظة"></textarea><button id="save-memory" type="button">حفظ التعليمات</button></details>
<details><summary>تنبيهات المخزون</summary><p id="inventory-status"></p><p>الحد: ٥٠ قطعة من مجموع مخزون المنتج. روابط الموردين للبحث فقط.</p><div id="inventory-alerts" style="max-height:200px;overflow:auto"></div></details>
<details><summary>الإعلانات: TikTok وFacebook وInstagram</summary><p id="marketing-status">جاري تحميل حالة الربط…</p><button type="button" id="marketing-report">قراءة نتائج آخر ٧ أيام</button><button type="button" id="marketing-plan">تحليل الإعلانات وتحضير خطة</button><div id="marketing-results" style="max-height:200px;overflow:auto"></div></details>
<details><summary>إجراءات تنتظر موافقتي</summary><p>راجعي التغيير قبل الموافقة. هذه النسخة تدعم عنوان ووصف المنتج وإيقاف حملة Meta.</p><div id="actions" style="max-height:200px;overflow:auto"></div></details>
</header>
<section id="messages" aria-live="polite">
<div class="bubble agent">أهلًا غصون، شو بتحبي نحلّل بمتجرك اليوم؟</div>
</section>
<div id="status" role="status"></div>
<form id="form">
<textarea id="input" rows="2" maxlength="4000"
aria-label="رسالتك" placeholder="اكتبي رسالتك هنا…" required></textarea>
<button id="send" type="submit">إرسال</button>
</form>
</main>
<script>
const messages = document.getElementById('messages');
const input = document.getElementById('input');
const send = document.getElementById('send');
const status = document.getElementById('status');

const face = document.getElementById('face');
const mic = document.getElementById('mic');
const voice = document.getElementById('voice');
const replay = document.getElementById('replay');
const csrf = document.querySelector('meta[name=csrf-token]').content;
const synth = window.speechSynthesis;
send.disabled = true;
let voiceEnabled = false, lastAnswer = '', busy = false, listening = false;
function setFace(state) { face.className = state; }
function stopVoice() { if (synth) synth.cancel(); setFace(busy ? 'thinking' : listening ? 'listening' : ''); }
function speechText(text) {
  const arabic = /[\u0600-\u06ff]/.test(text);
  let clean = String(text)
    .replace(/```[\s\S]*?```/g, '')
    .replace(/!?\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/https?:\/\/\S+/g, '')
    .replace(/^\s*\|?[\s:|-]*-{3,}[\s:|-]*\|?\s*$/gm, '')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*[-*+>]\s+/gm, '')
    .replace(/[|]/g, arabic ? '، ' : ', ')
    .replace(/[*_`~]/g, '')
    .replace(/[\p{Extended_Pictographic}\uFE0F\u200D\u20E3]/gu, '')
    .replace(/[ \t]+/g, ' ')
    .split('\n').map(line => line.replace(/^[\s,،]+|[\s,،]+$/g, '')).filter(Boolean).join('. ');
  if (arabic) {
    clean = clean.replace(/\$\s*(\d+)(?:\.(\d{1,2}))?/g, (_, dollars, cents) =>
      dollars + ' دولار' + (cents && Number(cents) ? ' و' + cents.padEnd(2, '0') + ' سنت' : ''));
  }
  return clean.trim();
}

function speak(text) {
  if (!synth) return;
  text = speechText(text);
  if (!text) return;
  stopVoice();
  const utterance = new SpeechSynthesisUtterance(text);
  const arabic = /[\u0600-\u06ff]/.test(text);
  utterance.lang = arabic ? 'ar-SA' : 'en-US';
  const available = synth.getVoices().find(v => v.lang.startsWith(arabic ? 'ar' : 'en'));
  if (available) utterance.voice = available;
  utterance.onstart = () => setFace('speaking');
  utterance.onend = () => setFace(busy ? 'thinking' : '');
  utterance.onerror = () => { setFace(''); status.textContent = 'تعذّر تشغيل الصوت. تحققي من أصوات الجهاز.'; };
  synth.speak(utterance);
}
voice.disabled = !synth;
replay.addEventListener('click', () => speak(lastAnswer));
voice.addEventListener('click', () => {
  voiceEnabled = !voiceEnabled;
  voice.textContent = voiceEnabled ? 'الصوت: مفعّل' : 'الصوت: متوقف';
  voice.setAttribute('aria-pressed', String(voiceEnabled));
  if (!voiceEnabled) stopVoice();
});
document.getElementById('stop').addEventListener('click', stopVoice);
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition;
if (Recognition && window.isSecureContext) {
  recognition = new Recognition(); recognition.lang = 'ar-SA'; recognition.interimResults = false;
  recognition.onstart = () => { listening = true; mic.textContent = 'إيقاف الإملاء'; setFace('listening'); status.textContent = 'عم اسمعك… احكي رسالتك، وبعدها اضغطي إرسال.'; };
  recognition.onresult = event => { input.value = (input.value + ' ' + event.results[0][0].transcript).trim().slice(0,4000); };
  recognition.onerror = event => { status.textContent = event.error === 'not-allowed' ? 'اسمحي للمتصفح باستخدام الميكروفون من إعدادات الموقع.' : 'تعذّر الإملاء الصوتي. جرّبي مجددًا أو اكتبي رسالتك.'; };
  recognition.onend = () => { listening = false; mic.textContent = '🎤 إملاء رسالة'; setFace(busy ? 'thinking' : ''); if (status.textContent.startsWith('عم اسمعك')) status.textContent = 'راجعي الرسالة واضغطي إرسال.'; };
  mic.addEventListener('click', () => { if (listening) recognition.stop(); else { stopVoice(); try { recognition.start(); } catch { status.textContent = 'انتظري انتهاء الإملاء ثم جرّبي مجددًا.'; } } });
} else { mic.disabled = true; mic.textContent = 'الإملاء غير متاح بهذا المتصفح'; }
window.addEventListener('pagehide', () => { if (recognition) recognition.abort(); if (synth) synth.cancel(); });

function add(text, role) {
  const bubble = document.createElement('div');
  bubble.className = 'bubble ' + role;
  bubble.dir = 'auto';
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
}

document.getElementById('form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message || send.disabled) return;
  if (recognition && listening) recognition.stop();
  stopVoice(); busy = true; setFace('thinking'); mic.disabled = true;
  add(message, 'user');
  input.value = '';
  send.disabled = true;
  status.textContent = 'الوكيل عم يحضّر الرد…';
  try {
    const response = await fetch('/ai/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': csrf},
      body: JSON.stringify({message: message})
    });
    if (response.status === 401) { window.location.href = '/login'; return; }
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error(data.error || 'تعذّر الحصول على الرد. جرّبي مرة ثانية.');
    }
    lastAnswer = data.answer || '';
    add(lastAnswer || 'لم يصل نص الرد.', 'agent');
    loadActions();
    replay.disabled = !lastAnswer || !synth;
    if (voiceEnabled && lastAnswer) speak(lastAnswer);
  } catch (error) {
    add(error.message || 'حدث خطأ بالاتصال.', 'agent');
  } finally {
    busy = false;
    if (face.className !== 'speaking') setFace('');
    mic.disabled = !recognition;
    send.disabled = false;
    status.textContent = '';
    input.focus();
  }
});

async function loadMemory() {
  try {
    const responses = await Promise.all([fetch('/ai/history'), fetch('/ai/memory')]);
    if (responses.some(r => r.status === 401)) { window.location.href = '/login'; return; }
    if (responses.some(r => !r.ok)) throw new Error('تعذّر تحميل الذاكرة. حدّثي الصفحة للمحاولة مجددًا.');
    const [history, memory] = await Promise.all(responses.map(r => r.json()));
    if (history.messages.length) messages.replaceChildren();
    history.messages.forEach(item => add(item.content, item.role === 'user' ? 'user' : 'agent'));
    const last = [...history.messages].reverse().find(item => item.role === 'assistant');
    lastAnswer = last ? last.content : ''; replay.disabled = !lastAnswer || !synth;
    document.getElementById('preferences').value = memory.instructions;
    send.disabled = false;
  } catch (error) { status.textContent = error.message; }
}
document.getElementById('save-memory').addEventListener('click', async () => {
  try {
    const response = await fetch('/ai/memory', {method:'PUT', headers:{'Content-Type':'application/json','X-CSRF-Token':csrf}, body:JSON.stringify({instructions:document.getElementById('preferences').value})});
    if (!response.ok) throw new Error('تعذّر حفظ التعليمات.');
    status.textContent = 'تم حفظ تعليماتك.';
  } catch(error) { status.textContent = error.message; }
});
document.getElementById('logout').addEventListener('click', async () => {
  stopVoice();
  await fetch('/logout', {method:'POST',headers:{'X-CSRF-Token':csrf}});
  window.location.href = '/login';
});

async function loadInventoryAlerts() {
  const notice = document.getElementById('inventory-status');
  try {
    const response = await fetch('/ai/inventory/alerts');
    if (response.status === 401) { window.location.href = '/login'; return; }
    if (!response.ok) throw new Error();
    const data = await response.json();
    const checked = data.checked_at ? new Date(data.checked_at) : null;
    notice.textContent = !checked ? 'المراقبة بانتظار تشغيل خدمة المخزون.' :
      (Date.now() - checked.getTime() > 1800000 ? 'المراقبة متأخرة؛ آخر فحص: ' : 'آخر فحص: ') + checked.toLocaleString();
    const list = document.getElementById('inventory-alerts');
    list.replaceChildren();
    if (!data.alerts.length) {
      const empty = document.createElement('p');
      empty.textContent = checked ? 'لا توجد تنبيهات محفوظة.' : 'سيظهر التنبيه هنا بعد أول فحص.';
      list.append(empty);
    }
    for (const alert of data.alerts) {
      const item = document.createElement('div');
      item.className = 'bubble agent';
      const title = document.createElement('p');
      title.textContent = alert.title + ' — المخزون وقت التنبيه: ' + alert.quantity +
        ' — ' + new Date(alert.created_at).toLocaleString();
      item.append(title);
      const link = document.createElement('a');
      link.textContent = 'البحث عن مورد على AliExpress';
      link.href = alert.supplier_search_url;
      link.target = '_blank'; link.rel = 'noopener noreferrer'; link.style.color = '#eac884';
      item.append(link);
      if (!alert.acknowledged) {
        const button = document.createElement('button');
        button.textContent = 'تم الاطلاع'; button.type = 'button';
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            const r = await fetch('/ai/inventory/alerts/' + alert.id + '/acknowledge', {
              method:'POST', headers:{'X-CSRF-Token':csrf}});
            if (!r.ok) throw new Error();
            await loadInventoryAlerts();
          } catch { notice.textContent = 'تعذّر حفظ حالة التنبيه.'; button.disabled = false; }
        });
        item.append(button);
      }
      list.append(item);
    }
  } catch { notice.textContent = 'تعذّر تحميل التنبيهات. ستتم إعادة المحاولة.'; }
}

async function loadMarketingStatus() {
  try {
    const response = await fetch('/ai/marketing/status');
    if (!response.ok) throw new Error();
    const data = await response.json();
    document.getElementById('marketing-status').textContent = Object.entries(data.platforms).map(([name,p]) =>
      (name === 'meta' ? 'Facebook وInstagram' : 'TikTok') + ': ' +
      (p.configured ? 'البيانات مُعدّة، التحقق عند قراءة التقرير' : 'بانتظار إعداد الربط')).join(' — ');
  } catch { document.getElementById('marketing-status').textContent = 'تعذّر قراءة حالة الربط.'; }
}
document.getElementById('marketing-report').addEventListener('click', async (event) => {
  const button = event.currentTarget;
  const output = document.getElementById('marketing-results');
  button.disabled = true; output.textContent = 'جاري قراءة التقارير…';
  try {
    const response = await fetch('/ai/marketing/report');
    if (!response.ok) throw new Error();
    const data = await response.json();
    output.replaceChildren();
    for (const [platform,report] of Object.entries(data.reports)) {
      const text = document.createElement('p');
      if (!report.verified) {
        text.textContent = platform + ': ' + (report.error || 'بانتظار الربط');
        output.append(text); continue;
      }
      text.textContent = platform + ' — ' + report.start_date + ' إلى ' + report.end_date;
      output.append(text);
      if (!report.rows.length) {
        const empty = document.createElement('p'); empty.textContent = 'لا توجد نتائج في هذه المدة.'; output.append(empty);
      }
      for (const row of report.rows) {
        const line = document.createElement('p');
        line.textContent = (row.campaign_name || row.campaign_id) + ' (' + row.placement + ')' +
          ' — الإنفاق: ' + (row.spend ?? 'غير متاح') + ' ' + (row.currency || '(العملة تحتاج تأكيد)') +
          ' — الظهور: ' + (row.impressions ?? 'غير متاح') + ' — النقرات: ' + (row.clicks ?? 'غير متاح');
        output.append(line);
      }
    }
  } catch { output.textContent = 'تعذّر تحميل التقرير.'; }
  finally { button.disabled = false; }
});
document.getElementById('marketing-plan').addEventListener('click', () => {
  input.value = 'حلّل بيانات الإعلانات المتاحة على TikTok وFacebook وInstagram مع بيانات المتجر. اذكر الحسابات غير المتصلة، واقترح خطة إعلانات عملية ونصوصًا للمنتجات المتوفرة. ميّز بين النقرات والتحويلات والمشتريات المؤكدة، ولا تفترض ميزانية أو تشغّل إعلانًا.';
  input.focus();
});
async function loadActions() {
  const list = document.getElementById('actions');
  try {
    const response = await fetch('/ai/actions');
    if (!response.ok) throw new Error();
    const data = await response.json();
    list.replaceChildren();
    if (!data.actions.length) list.textContent = 'لا توجد إجراءات محفوظة.';
    for (const action of data.actions) {
      const item = document.createElement('div'); item.className = 'bubble agent';
      const text = document.createElement('p');
      const old = action.kind === 'product_title' ? action.before.title : action.kind === 'product_description' ? action.before.descriptionHtml : action.before.status;
      const states = {pending:'بانتظار الموافقة',completed:'تم التنفيذ',rejected:'مرفوض',failed:'فشل التنفيذ',expired:'انتهت صلاحية الاقتراح',needs_review:'راجعي المنصة؛ نتيجة التنفيذ غير مؤكدة'};
      text.textContent = action.kind + ' — ' + action.target + '\nالسبب: ' + action.reason + '\nقبل: ' + old + '\nبعد: ' + action.content + '\nالحالة: ' + (states[action.state] || action.state);
      item.append(text);
      if (action.state === 'pending') {
        for (const [decision,label] of [['approve','موافقة وتنفيذ'],['reject','رفض']]) {
          const button = document.createElement('button'); button.type='button'; button.textContent=label;
          button.addEventListener('click', async () => {
            button.disabled=true;
            try {
              const r=await fetch('/ai/actions/'+action.id+'/'+decision,{method:'POST',headers:{'X-CSRF-Token':csrf}});
              const result=await r.json();
              if(!r.ok) throw new Error(result.error || 'تعذّر حفظ القرار.');
              await loadActions();
            } catch(error) { status.textContent=error.message; await loadActions(); }
          });
          item.append(button);
        }
      }
      list.append(item);
    }
  } catch { list.textContent = 'تعذّر تحميل الإجراءات.'; }
}
loadActions();
loadMarketingStatus();
loadInventoryAlerts();
const inventoryTimer = setInterval(loadInventoryAlerts, 60000);
window.addEventListener('pagehide', () => clearInterval(inventoryTimer));
loadMemory();
</script>
</body>
</html>
"""


@chat_ui.route("/assistant", methods=["GET"])
def assistant_page():
    return Response(PAGE.replace("{{ csrf_token() }}", csrf_token()), mimetype="text/html")

