from flask import Blueprint, Response

chat_ui = Blueprint("chat_ui", __name__)

PAGE = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Luree AI Agent</title>
<style>
*{box-sizing:border-box}
body{margin:0;background:#10121a;color:#eee;
font-family:Arial,sans-serif}
main{max-width:760px;margin:auto;height:100dvh;
display:flex;flex-direction:column;padding:18px}
header{padding:12px 0;border-bottom:1px solid #333}
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
#face{width:86px;height:86px;border:2px solid #eac884;border-radius:45%;background:#222633;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:15px;flex-shrink:0}
.eyes{display:flex;gap:23px}.eye{width:10px;height:13px;border-radius:50%;background:#eac884}
.mouth{width:28px;height:8px;border-bottom:3px solid #eac884;border-radius:50%}
#face.thinking .eye{animation:blink 1s infinite}
#face.speaking .mouth{background:#eac884;animation:talk .3s infinite alternate}
#face.listening{box-shadow:0 0 20px #eac884}
.controls{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.controls button{padding:8px 12px;font-size:14px}
@keyframes blink{50%{transform:scaleY(.2)}}@keyframes talk{to{height:18px}}
@media(prefers-reduced-motion:reduce){#face .eye,#face .mouth{animation:none!important}}
</style>
</head>
<body>
<main>
<header>
<div class="identity"><div id="face" role="img" aria-label="وجه الوكيل"><div class="eyes"><span class="eye"></span><span class="eye"></span></div><div class="mouth"></div></div><div><h1>Luree AI Agent</h1><p>مساعدك لإدارة وتحليل متجر Luree Fashions</p></div></div>
<div class="controls"><button id="mic" type="button">🎤 إملاء رسالة</button><button id="voice" type="button" aria-pressed="false">الصوت: متوقف</button><button id="replay" type="button" disabled>قراءة آخر رد</button><button id="stop" type="button">إيقاف الصوت</button></div>
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
const synth = window.speechSynthesis;
let voiceEnabled = false, lastAnswer = '', busy = false, listening = false;
function setFace(state) { face.className = state; }
function stopVoice() { if (synth) synth.cancel(); setFace(busy ? 'thinking' : listening ? 'listening' : ''); }
function speak(text) {
  if (!synth) return;
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
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: message})
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      throw new Error('تعذّر الحصول على الرد. جرّبي مرة ثانية.');
    }
    lastAnswer = data.answer || '';
    add(lastAnswer || 'لم يصل نص الرد.', 'agent');
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
</script>
</body>
</html>
"""


@chat_ui.route("/assistant", methods=["GET"])
def assistant_page():
    return Response(PAGE, mimetype="text/html")
