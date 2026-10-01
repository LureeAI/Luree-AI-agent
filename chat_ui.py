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
</style>
</head>
<body>
<main>
<header>
<h1>Luree AI Agent</h1>
<p>مساعدك لإدارة وتحليل متجر Luree Fashions</p>
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
    add(data.answer || 'لم يصل نص الرد.', 'agent');
  } catch (error) {
    add(error.message || 'حدث خطأ بالاتصال.', 'agent');
  } finally {
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
