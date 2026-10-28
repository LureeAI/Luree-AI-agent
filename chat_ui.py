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
#product-preparer label{display:block;margin:8px 0}
#product-preparer textarea{display:block;width:100%}
#product-preparer select{max-width:100%;padding:8px}
#product-preparer input:not([type=checkbox]){max-width:100%;padding:8px}
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
<details><summary>الإعلانات: TikTok وFacebook وInstagram</summary><p id="marketing-status">جاري تحميل حالة الربط…</p><button type="button" id="marketing-verify">فحص ربط ميتا</button><p id="marketing-verification" role="status"></p><button type="button" id="marketing-report">قراءة نتائج آخر ٧ أيام</button><button type="button" id="marketing-plan">تحليل الإعلانات وتحضير خطة</button><div id="marketing-results" style="max-height:200px;overflow:auto"></div>
<h3>أرشيف نتائج الحملات</h3><p>يحفظ نتائج الأيام المكتملة. المزامنة للقراءة فقط، وتحتاج تشغيل عامل الأرشفة وصلاحيات المنصة. لا تشغّل إعلانات.</p>
<label>المنصة <select id="ads-platform"><option value="meta">Facebook وInstagram</option><option value="tiktok">TikTok</option></select></label>
<label>من <input type="date" id="ads-start"></label><label>إلى <input type="date" id="ads-end"></label>
<button type="button" id="ads-sync">طلب حفظ النتائج (حتى ٣١ يومًا)</button>
<button type="button" id="ads-status">تحديث حالة الأرشيف</button><p id="ads-notice" role="status"></p>
<label>الحساب المحفوظ <select id="ads-account"></select></label>
<label>المستوى <select id="ads-level"><option value="campaign">الحملات</option><option value="adgroup">المجموعات الإعلانية</option><option value="ad">الإعلانات</option></select></label>
<button type="button" id="ads-history">قراءة النتائج المحفوظة</button>
<pre id="ads-history-result" style="white-space:pre-wrap;max-height:350px;overflow:auto"></pre>
<h3>تحليل الربحية ومراجعة القرارات</h3>
<p>اختاري الحساب والتواريخ والمستوى أعلاه. التكاليف التالية متوسطات لكل طلب بعملة حساب الإعلان، وليست لكل قطعة. اتركي المجهول فارغًا؛ لا يعتبره لوري صفرًا.</p>
<label>عملة التكاليف <input id="mgr-currency" maxlength="3" placeholder="USD"></label>
<label>اسم حدث الشراء المطابق للتقرير <input id="mgr-event" placeholder="مثال: offsite_conversion.fb_pixel_purchase"></label>
<label>حدث مشاهدة صفحة الوصول <input id="mgr-lpv" placeholder="اسم الحدث كما يظهر بالتقرير"></label>
<label>حدث الإضافة للسلة <input id="mgr-cart" placeholder="اسم الحدث كما يظهر بالتقرير"></label>
<label>حدث بدء الدفع <input id="mgr-checkout" placeholder="اسم الحدث كما يظهر بالتقرير"></label>
<label>تكلفة المنتجات لكل طلب <input id="mgr-product" type="number" min="0" step="any"></label>
<label>الشحن لكل طلب <input id="mgr-shipping" type="number" min="0" step="any"></label>
<label>رسوم الدفع ٪ من الإيراد <input id="mgr-percent" type="number" min="0" max="100" step="any"></label>
<label>رسوم ثابتة لكل طلب <input id="mgr-fixed" type="number" min="0" step="any"></label>
<label>تقدير المرتجعات ٪ من الإيراد <input id="mgr-refund" type="number" min="0" max="100" step="any"></label>
<label>الضرائب ٪ من الإيراد <input id="mgr-tax" type="number" min="0" max="100" step="any"></label>
<label>حد تنبيه الصرف اليومي <input id="mgr-limit" type="number" min="0" step="any"></label>
<label><input id="mgr-basis" type="checkbox">تأكدت أن قيمة حدث الشراء تمثل الإيراد قبل خصم المرتجعات والضرائب</label>
<label><input id="mgr-monitor" type="checkbox">تفعيل تحديث وتحليل دوري كل ساعة عند تشغيل عامل الأرشفة</label>
<p>قواعد البداية قابلة للتعديل عبر السياسة: ١٠٠٠ ظهور، ٥٠ نقرة، ٥ مشتريات، مهلة تحويل يومان، واقتراح زيادة أقصاه ١٥٪. هذه حدود إرشادية وليست إثباتًا إحصائيًا. الأرباح تقديرية ولا تشمل مصاريف لم تدخليها.</p>
<button type="button" id="mgr-load">تحميل سياسة الحساب</button><button type="button" id="mgr-save">حفظ التكاليف والسياسة</button>
<button type="button" id="mgr-analyze">تحليل الفترة ومقارنتها</button><button type="button" id="mgr-refresh">تحديث التحليلات والتنبيهات</button>
<button type="button" id="mgr-reconcile">مراجعة المشتريات مقابل شوبيفاي</button>
<label>رابط المنتج للتتبّع <input id="mgr-url" type="url" placeholder="https://..."></label>
<label>رقم الحملة <input id="mgr-campaign" inputmode="numeric"></label><label>رقم الإعلان <input id="mgr-ad" inputmode="numeric"></label>
<button type="button" id="mgr-track">تجهيز رابط UTM فقط</button><p id="mgr-notice" role="status"></p><pre id="mgr-reconciliation" style="white-space:pre-wrap"></pre><div id="mgr-results"></div><div id="mgr-alerts"></div></details>
<details><summary>إجراءات تنتظر موافقتي</summary><p>راجعي التغيير قبل الموافقة. هذه النسخة تدعم عنوان ووصف المنتج وإيقاف حملة Meta.</p><div id="actions" style="max-height:200px;overflow:auto"></div></details>
<details id="product-preparer"><summary>تجهيز فستان ومناقشة سعره</summary>
<details id="prep-import-list"><summary>Import List — قائمة الاستيراد</summary>
<p>هذا القسم مخصص للفساتين الموجودة في قائمة الاستيراد في DSers قبل نقلها إلى Shopify.</p>
<p role="status">قائمة DSers غير متصلة بالوكيل حاليًا؛ لا يمكن عرض فساتينها أو تعديلها هنا بعد.</p>
<a href="https://www.dsers.com/application/import_list" target="_blank" rel="noopener noreferrer">فتح Import List في DSers</a>
<p>للعمل الآن: انقلي الفستان من DSers إلى Shopify كمسودة مع ربط المورّد، ثم اختاريه من My Products أدناه. مسودة Shopify ليست قائمة DSers.</p>
</details>
<details id="prep-my-products" open><summary>My Products — منتجاتي في Shopify</summary>
<p>منتجات Shopify الحالية، بما فيها المسودات والمنشورة. هذه القائمة تُقرأ من Shopify وليست مزامنة لقائمة My Products في DSers.</p>
<p>استوردي الفستان عبر DSers إلى Shopify كمسودة أولًا، مع ربط المورّد. هنا نجهّز النصوص والسعر وترتيب الصور دون تغيير الألوان والمقاسات أو معرّفاتها. التحقق المباشر من مخزون المورّد غير متاح بعد.</p>
<label>الفستان <select id="prep-product"><option value="">اختاري الفستان…</option></select></label>
<p id="prep-stock"></p>
<div style="display:grid;gap:8px">
<label>سعر البيع المقترح لكل المقاسات <input id="prep-price" type="number" min="0.01" step="0.01"></label>
<label>أعلى تكلفة شراء بين الخيارات <input id="prep-cost" type="number" min="0" step="0.01"></label>
<label>تكلفة الشحن <input id="prep-shipping" type="number" min="0" step="0.01"></label>
<label>رسوم الدفع ٪ <input id="prep-fee" type="number" min="0" max="99.99" step="0.01"></label>
<label>رسوم ثابتة <input id="prep-fixed" type="number" min="0" step="0.01"></label>
</div>
<p>كل المبالغ بعملة المتجر. اتركي المجهول فارغًا؛ أدخلي صفرًا فقط إذا تأكدتِ أنه صفر. الحساب لا يشمل الإعلان والضرائب والمرتجعات.</p>
<button id="prep-review" type="button">احسبي السعر والربح</button><button id="prep-discuss" type="button">ناقشي السعر مع الوكيل</button>
<p id="prep-price-result" style="white-space:pre-wrap"></p>
<label>توجيهاتك للنص <textarea id="prep-notes" maxlength="2000" rows="2"></textarea></label>
<button id="prep-generate" type="button">جهّزي النصوص وترتيب الصور</button>
<p>التجهيز يرسل معلومات المنتج وحتى ١٢ صورة إلى OpenAI ويستهلك الرصيد. يرتّب الصور الموجودة ولا يعيد رسم الفستان. النصوص للمتجر بالإنكليزية، وبتقدري تعدليها قبل الموافقة.</p>
<label>الاسم <textarea id="prep-title" maxlength="255" rows="2"></textarea></label>
<label>الوصف وجدول المقاسات المتوفر <textarea id="prep-description" maxlength="6000" rows="5"></textarea></label>
<label>عنوان البحث <textarea id="prep-seo-title" maxlength="70" rows="1"></textarea></label>
<label>وصف البحث <textarea id="prep-seo-description" maxlength="320" rows="2"></textarea></label>
<p>ترتيب الصور: اختاري الصورة الرئيسية وانقلي الصور للأعلى أو الأسفل. لا تُحذف الصور ولا تتغير صور الخيارات المرتبطة.</p>
<div id="prep-media"></div>
<label>رابط المورّد (للتوثيق فقط) <input id="prep-supplier" type="url"></label>
<label><input id="prep-confirm" type="checkbox"> راجعت بنفسي ربط المورّد وتوفر الألوان والمقاسات في DSers/AliExpress</label>
<label>النشر بعد الموافقة <select id="prep-publication"><option value="">تعديل فقط؛ الحفاظ على حالة النشر الحالية</option></select></label>
<p id="prep-channel-note"></p>
<p>السعر المدخل سيطبّق على كل الخيارات، وسيُزال سعر المقارنة القديم لتجنب عرض خصم غير صحيح. إذا المنتج منشور حاليًا، التعديلات ستظهر عليه عند التنفيذ. اختيار النشر يفعّل المنتج وقد يجعله ظاهرًا أيضًا في القنوات المرتبط بها سابقًا.</p>
<button id="prep-save" type="button">حفظ معاينة للموافقة</button><p id="prep-status" role="status"></p>
<div id="prep-list"></div>
</details>
</details>

<details id="video-builder"><summary>إنشاء فيديو فستان</summary>
<p>فيديو عمودي ١٥ ثانية: افتتاحية، صور المنتج بحركة وانتقالات، موسيقى أصلية، السعر، ودعوة للشراء. اختاري صور اللون المطلوب.</p>
<label>الفستان <select id="video-product" style="max-width:100%;padding:8px"><option value="">اختاري الفستان…</option></select></label>
<div id="video-photos" style="display:flex;flex-wrap:wrap;gap:8px;max-height:230px;overflow:auto"></div>
<label><input id="video-price" type="checkbox" checked> إظهار السعر (من… إذا اختلف بين المقاسات)</label>
<label><input id="video-voice" type="checkbox" checked> إضافة تعليق صوتي بالذكاء الاصطناعي (يستهلك من رصيد OpenAI)</label><p>اختاري لغة واحدة أو ٣ نسخ من نفس الفيديو. لكل نسخة صوت باللغة المختارة، وكل تعليق يستهلك رصيد OpenAI. الصوت اصطناعي. النصوص الافتراضية متاحة باللغات الثلاث؛ يمكنك تعديلها (٤٠ كلمة، ٣٠٠ حرف لكل نص).</p>
<select id="video-language" aria-label="لغة الفيديو"><option value="all">٣ نسخ: عربي + إنكليزي + كوري</option><option value="ar">عربي</option><option value="en">إنكليزي</option><option value="ko">كوري</option></select>
<label>النص العربي<textarea id="video-narration-ar" maxlength="300" rows="2" placeholder="اتركيه فارغًا للنص العربي الافتراضي"></textarea></label>
<label>English<textarea id="video-narration-en" maxlength="300" rows="2" placeholder="Leave empty for the default English script"></textarea></label>
<label>한국어<textarea id="video-narration-ko" maxlength="300" rows="2" placeholder="기본 한국어 문구를 사용하려면 비워 두세요"></textarea></label>
<button type="button" id="create-video" disabled>إنشاء فيديو ١٥ ثانية</button>
<p id="video-status" role="status"></p>
<div id="video-list" style="max-height:250px;overflow:auto"></div></details>

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
      if (report.account) {
        const account=document.createElement('p'); account.textContent=report.account.name+' — '+report.account.currency+' — '+report.account.timezone; output.append(account);
      }
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
document.getElementById('marketing-verify').addEventListener('click', async (event) => {
  const button=event.currentTarget, output=document.getElementById('marketing-verification');
  button.disabled=true; output.textContent='جاري فحص الحساب وصلاحية قراءة التقرير…';
  try {
    const response=await fetch('/ai/marketing/verify');
    if(!response.ok) throw new Error();
    const {meta}=await response.json();
    output.textContent=meta.verified ?
      'تم التحقق من قراءة التقرير — '+meta.account.name+' — رقم الحساب: '+meta.account.id+' — العملة: '+meta.account.currency+' — التوقيت: '+meta.account.timezone+' — مهام الحساب: '+(meta.account.tasks.join(', ') || 'غير متاحة')+' — تاريخ انتهاء المفتاح غير معروف.' :
      (meta.error || 'يلزم إعداد: '+(meta.missing || []).join(', '));
  } catch { output.textContent='تعذّر فحص الربط. لم يتم تأكيد الاتصال.'; }
  finally { button.disabled=false; }
});
document.getElementById('marketing-plan').addEventListener('click', () => {
  input.value = 'حلّل بيانات الإعلانات المتاحة على TikTok وFacebook وInstagram مع بيانات المتجر. اذكر الحسابات غير المتصلة، واقترح خطة إعلانات عملية ونصوصًا للمنتجات المتوفرة. ميّز بين النقرات والتحويلات والمشتريات المؤكدة، ولا تفترض ميزانية أو تشغّل إعلانًا.';
  input.focus();
});

async function loadAdArchive() {
  const out=document.getElementById('ads-notice');
  try {
    const r=await fetch('/ai/marketing/archive/status');const data=await r.json();
    if(!r.ok || !data.success) throw new Error(data.error || 'تعذّر قراءة الأرشيف');
    const select=document.getElementById('ads-account');select.replaceChildren();
    for(const a of data.accounts){const option=document.createElement('option');
      option.value=JSON.stringify({platform:a.platform,id:a.id});
      option.textContent=a.platform+' — '+(a.name||a.id)+' — '+a.currency+' — '+a.timezone;
      select.append(option);}
    out.textContent=(data.accounts.length ? 'الحسابات المحفوظة: '+data.accounts.length : 'الأرشيف جاهز، لم تُحفظ بيانات حسابات بعد.')+
      ' | آخر الطلبات: '+data.recent_runs.slice(0,4).map(j=>j.platform+' '+j.status+' ('+j.days_saved+' يوم)'+(j.error_code?' — '+j.error_code:'')).join('، ');
  }catch(e){out.textContent=e.message;}
}
document.getElementById('ads-status').addEventListener('click',loadAdArchive);
document.getElementById('ads-sync').addEventListener('click',async (event)=>{
  const b=event.currentTarget;b.disabled=true;
  try{
    const r=await fetch('/ai/marketing/sync',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
      body:JSON.stringify({platform:document.getElementById('ads-platform').value,start:document.getElementById('ads-start').value,end:document.getElementById('ads-end').value})});
    const data=await r.json();if(!r.ok || !data.success)throw new Error(data.error||'تعذّر طلب المزامنة');
    document.getElementById('ads-notice').textContent='تم تسجيل الطلب '+data.id+' بانتظار عامل الأرشفة. اضغطي تحديث الحالة لاحقًا؛ التسجيل ليس اكتمال المزامنة.';
  }catch(e){document.getElementById('ads-notice').textContent=e.message;}finally{b.disabled=false;}
});
document.getElementById('ads-history').addEventListener('click',async(event)=>{
  const b=event.currentTarget,out=document.getElementById('ads-history-result');b.disabled=true;
  try{
    const a=JSON.parse(document.getElementById('ads-account').value);
    const q=new URLSearchParams({platform:a.platform,account_id:a.id,start:document.getElementById('ads-start').value,end:document.getElementById('ads-end').value,level:document.getElementById('ads-level').value});
    const r=await fetch('/ai/marketing/archive?'+q);const data=await r.json();
    if(!r.ok || !data.success)throw new Error(data.error||'تعذّر قراءة النتائج');
    const report=data.report;
    out.textContent='بيانات محفوظة وليست مباشرة — '+report.start_date+' إلى '+report.end_date+'\n'+
      'العملة: '+(report.account?.currency||'غير متاحة')+' — الأيام الناقصة: '+(report.missing_dates.join(', ')||'لا يوجد')+'\n'+
      'آخر حفظ للأيام: '+report.days.map(d=>d.date+' / '+d.saved_at).join('، ')+'\n'+
      JSON.stringify(report.totals_for_available_days,null,2)+'\nالتحويلات منسوبة للمنصة وليست طلبات مؤكدة. افتحي المحادثة لطلب تحليل الأرشيف.';
  }catch(e){out.textContent=e.message||'اختاري حسابًا محفوظًا وتواريخ.';}finally{b.disabled=false;}
});
loadAdArchive();


const costFields={product_cost_per_order:'mgr-product',shipping_cost_per_order:'mgr-shipping',payment_fee_percent:'mgr-percent',fixed_fee_per_order:'mgr-fixed',refund_rate_percent:'mgr-refund',tax_percent_of_revenue:'mgr-tax'};
let managerRules={};
document.getElementById('ads-account').addEventListener('change',()=>{managerRules={};for(const id of Object.values(costFields))document.getElementById(id).value='';for(const id of ['mgr-event','mgr-currency','mgr-limit','mgr-lpv','mgr-cart','mgr-checkout'])document.getElementById(id).value='';document.getElementById('mgr-basis').checked=false;document.getElementById('mgr-monitor').checked=false;document.getElementById('mgr-results').replaceChildren();document.getElementById('mgr-alerts').replaceChildren();document.getElementById('mgr-notice').textContent='تم تغيير الحساب؛ حمّلي سياسته أو أدخلي تكاليفه.';});
function managerAccount(){return JSON.parse(document.getElementById('ads-account').value);}
async function managerRequest(path,method='GET',body){
  const r=await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},...(body?{body:JSON.stringify(body)}:{})});
  const d=await r.json();if(!r.ok||!d.success)throw new Error(d.error||'تعذّر إكمال الطلب');return d;
}
async function managerAction(fn){try{await fn();}catch(e){document.getElementById('mgr-notice').textContent=e.message||'اختاري حسابًا محفوظًا أولًا.';}}
document.getElementById('mgr-load').onclick=()=>managerAction(async()=>{
  const a=managerAccount(),d=await managerRequest('/ai/marketing/policy?'+new URLSearchParams({platform:a.platform,account_id:a.id}));
  const p=d.policy;if(!p)throw new Error('لا توجد سياسة محفوظة لهذا الحساب؛ أدخلي التكاليف المعروفة.');
  managerRules=p.rules;for(const [k,id]of Object.entries({landing_page_view:'mgr-lpv',add_to_cart:'mgr-cart',initiate_checkout:'mgr-checkout'}))document.getElementById(id).value=p.funnel_events?.[k]||'';document.getElementById('mgr-currency').value=p.currency;document.getElementById('mgr-event').value=p.purchase_event||'';
  for(const [k,id] of Object.entries(costFields))document.getElementById(id).value=p.costs[k]??'';
  document.getElementById('mgr-limit').value=p.daily_spend_limit??'';document.getElementById('mgr-basis').checked=!!p.purchase_value_basis;document.getElementById('mgr-monitor').checked=p.monitoring_enabled;
  document.getElementById('mgr-notice').textContent='تم تحميل سياسة الحساب؛ راجعي التكاليف قبل الحفظ.';
});
document.getElementById('mgr-save').onclick=()=>managerAction(async()=>{
  const a=managerAccount(),costs={};for(const[k,id]of Object.entries(costFields))costs[k]=document.getElementById(id).value||null;
  const p={currency:document.getElementById('mgr-currency').value.trim().toUpperCase(),purchase_event:document.getElementById('mgr-event').value.trim()||null,
    funnel_events:{landing_page_view:document.getElementById('mgr-lpv').value.trim()||null,add_to_cart:document.getElementById('mgr-cart').value.trim()||null,initiate_checkout:document.getElementById('mgr-checkout').value.trim()||null},purchase_value_basis:document.getElementById('mgr-basis').checked?'revenue_before_refunds_and_taxes':null,costs,rules:managerRules,
    daily_spend_limit:document.getElementById('mgr-limit').value||null,monitoring_enabled:document.getElementById('mgr-monitor').checked};
  for(const k of Object.keys(p.funnel_events))if(p.funnel_events[k]===null)delete p.funnel_events[k];
  const d=await managerRequest('/ai/marketing/policy','PUT',{platform:a.platform,account_id:a.id,policy:p});managerRules=d.policy.rules;
  document.getElementById('mgr-notice').textContent='تم حفظ السياسة. تفعيل المتابعة يحتاج عامل الأرشفة وصلاحيات المنصة؛ لا ينفذ إنفاقًا.';
});
const decisionNames={wait_for_data:'انتظار اكتمال البيانات',review_creative:'مراجعة الإعلان',request_data:'استكمال البيانات والتكاليف',continue_observation:'متابعة وجمع عينة أكبر',propose_pause:'اقتراح إيقاف للمراجعة',propose_budget_increase:'اقتراح زيادة محدودة للمراجعة',hold_budget:'الإبقاء على الميزانية',verify_shopify_before_scaling:'تأكيد طلبات شوبيفاي قبل زيادة الميزانية'};
function renderManagerAnalysis(a,id){
  const box=document.getElementById('mgr-results');box.replaceChildren();
  const head=document.createElement('p');head.textContent='تحليل '+a.start_date+' إلى '+a.end_date+' — '+a.currency+' — تحذيرات البيانات: '+(a.data_warnings.join(', ')||'لا يوجد')+' — لا تنفيذ تلقائي.';box.append(head);
  for(const e of a.entities){const card=document.createElement('section');card.style.border='1px solid #777';card.style.padding='12px';
    const h=document.createElement('h4');h.textContent=(e.entity_name||e.entity_id)+' — '+e.placement;card.append(h);
    const p=document.createElement('p'),m=e.metrics;p.textContent='الصرف: '+(m.spend??'غير متاح')+' — CPA شراء: '+(m.purchase_cpa??'غير متاح')+' — ROAS: '+(m.roas??'غير متاح')+' — مساهمة تقديرية بعد الإعلان: '+(m.estimated_contribution_after_ads??'التكاليف أو المشتريات غير مكتملة');card.append(p);
    for(const f of e.findings){const line=document.createElement('p');line.textContent=(decisionNames[f.decision]||f.decision)+' — '+f.reason;card.append(line);
      if(f.requires_owner_approval){for(const[outcome,label]of [['accepted_for_review','سجّل للمراجعة فقط'],['rejected','رفض الاقتراح'],['deferred','تأجيل']]){const b=document.createElement('button');b.type='button';b.textContent=label;b.onclick=()=>managerAction(async()=>{await managerRequest('/ai/marketing/decisions','POST',{analysis_id:id,entity_id:e.entity_id,placement:e.placement,code:f.code,outcome});document.getElementById('mgr-notice').textContent='سُجل القرار للمراجعة، ولم ينفذ أي تغيير أو صرف.';});card.append(b);}}
    }
    const diagnostic=a.diagnostics?.entities.find(x=>x.entity_id===e.entity_id&&x.placement===e.placement);
    if(diagnostic){const p=document.createElement('p');p.textContent='مسار الأحداث (ليست أعداد زوار فريدين): '+Object.entries(diagnostic.event_counts).map(([k,v])=>k+': '+(v??'غير متاح')).join(' — ');card.append(p);
      const v=document.createElement('p');v.textContent='معدل إكمال الفيديو: '+(diagnostic.video.completion_rate_percent??'غير متاح')+'٪ — معدّل مشاهدة ثانيتين: '+(diagnostic.video.two_second_view_rate_percent??'غير متاح')+'٪';card.append(v);}
    box.append(card);
  }
}
document.getElementById('mgr-analyze').onclick=()=>managerAction(async()=>{
  const a=managerAccount(),d=await managerRequest('/ai/marketing/analysis','POST',{platform:a.platform,account_id:a.id,start:document.getElementById('ads-start').value,end:document.getElementById('ads-end').value,level:document.getElementById('ads-level').value});
  renderManagerAnalysis(d.analysis,d.analysis.analysis_id);document.getElementById('mgr-notice').textContent='تم حفظ التحليل وأدلته؛ التوصيات تحتاج مراجعتك.';
});
document.getElementById('mgr-refresh').onclick=()=>managerAction(async()=>{
  const a=managerAccount(),d=await managerRequest('/ai/marketing/manager');
  document.getElementById('mgr-notice').textContent='حالة المتابعة: '+d.monitor_health.filter(x=>x.platform===a.platform&&x.account_id===a.id).map(x=>x.stage+': '+x.status+' ('+x.checked_at+')').join(' — ');
  const latest=d.analyses.find(x=>x.platform===a.platform&&x.account_id===a.id);if(latest)renderManagerAnalysis(latest.report,latest.id);
  const out=document.getElementById('mgr-alerts');out.replaceChildren();
  for(const alert of d.alerts.filter(x=>x.platform===a.platform&&x.account_id===a.id&&!x.acknowledged_at&&!x.resolved_at)){
    const p=document.createElement('p');p.textContent='تنبيه '+alert.created_at+' — '+(alert.evidence.reason||alert.evidence.code);
    const b=document.createElement('button');b.type='button';b.textContent='تمت المراجعة';b.onclick=()=>managerAction(async()=>{await managerRequest('/ai/marketing/alerts/'+alert.id+'/acknowledge','POST');p.remove();});p.append(b);out.append(p);
  }
});


document.getElementById('mgr-reconcile').onclick=()=>managerAction(async()=>{
  const a=managerAccount();document.getElementById('mgr-notice').textContent='جاري قراءة الطلبات المدفوعة والمرتجعات ومصدرها…';
  const d=await managerRequest('/ai/marketing/reconcile','POST',{platform:a.platform,account_id:a.id,start:document.getElementById('ads-start').value,end:document.getElementById('ads-end').value});
  const r=d.report;document.getElementById('mgr-reconciliation').textContent='طلبات مدفوعة ضمن طلبات الفترة: '+r.confirmed_paid_orders_in_cohort+'\nمبالغ محصّلة لمجموعة الطلبات غير التجريبية (تشمل الملغاة): '+r.cohort_total_received+' '+r.shop_currency+'\nمرتجعات: '+r.cohort_total_refunded+'\nصافي نقد هذه المجموعة: '+r.cohort_net_cash+'\nمشتريات منسوبة للمنصة: '+(r.platform_attributed_purchases??'غير متاحة')+'\nمطابقة حسب حملة UTM: '+r.matched_campaigns.map(x=>x.campaign_id+': '+x.paid_orders).join('، ')+'\nهذه مقارنة أدلة ومجموعة طلبات، وليست إثباتًا أن كل طلب سببه الإعلان أو أن فروق القيم تعني خللًا. الضرائب والشحن والإسناد والتواريخ قد تختلف.';
  document.getElementById('mgr-notice').textContent='حُفظت مراجعة المشتريات دون بيانات شخصية للعملاء.';
});
document.getElementById('mgr-track').onclick=()=>managerAction(async()=>{
  const a=managerAccount(),d=await managerRequest('/ai/marketing/tracking-url','POST',{destination:document.getElementById('mgr-url').value,platform:a.platform,campaign_id:document.getElementById('mgr-campaign').value,ad_id:document.getElementById('mgr-ad').value});
  document.getElementById('mgr-reconciliation').textContent=d.url+'\nرابط جاهز للنسخ، لم يُنشر ولم يتغير أي إعلان. يعمل للتتبّع المستقبلي فقط.';
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
      const states = {pending:'بانتظار الموافقة',executing:'بدأ التنفيذ؛ تحققي من الحالة قبل أي إجراء جديد',completed:'تم التنفيذ',rejected:'مرفوض',failed:'فشل التنفيذ',expired:'انتهت صلاحية الاقتراح',needs_review:'راجعي المنصة؛ نتيجة التنفيذ غير مؤكدة'};
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
      if (action.kind === 'meta_pause' && ['executing','needs_review'].includes(action.state)) {
        const button=document.createElement('button'); button.type='button'; button.textContent='التحقق من حالة الحملة دون إعادة الإيقاف';
        button.addEventListener('click',async () => {
          button.disabled=true;
          try {
            const response=await fetch('/ai/actions/'+action.id+'/reconcile',{method:'POST',headers:{'X-CSRF-Token':csrf}});
            const result=await response.json();
            if(!response.ok) throw new Error(result.error || 'تعذّر التحقق.');
            await loadActions();
          } catch(error) { status.textContent=error.message; button.disabled=false; }
        });
        item.append(button);
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

const videoBuilder=document.getElementById('video-builder');
const videoProduct=document.getElementById('video-product');
const createVideo=document.getElementById('create-video');
const videoStatus=document.getElementById('video-status');
let videosInitialized=false, videoBusy=false, videoSelectionVersion=0;
async function videoFetch(path,options={}) {
  const response=await fetch(path,options);
  if(response.status===401) { window.location.href='/login'; throw new Error('يلزم الدخول.'); }
  const data=await response.json();
  if(!response.ok || !data.success) throw new Error(data.error || 'تعذّر الوصول لخدمة الفيديو.');
  return data;
}
async function loadVideos() {
  if(!videoBuilder.open) return;
  try {
    const data=await videoFetch('/ai/videos');
    const list=document.getElementById('video-list');list.replaceChildren();
    const states={queued:'بانتظار خدمة التجهيز',rendering:'الفيديو عم يتجهّز',ready:'جاهز للتنزيل',failed:'تعذّر التجهيز؛ اختاري صورًا أخرى أو راجعي خدمة التجهيز'};
    for(const job of data.videos) {
      const item=document.createElement('div');item.className='bubble agent';
      const text=document.createElement('p');
      text.textContent=({'ar':'عربي','en':'إنكليزي','ko':'كوري'}[job.language]||'إنكليزي')+' — '+job.title+' — '+(job.include_voice ? 'موسيقى وتعليق صوتي' : 'موسيقى')+' — '+states[job.state]+' — '+new Date(job.created_at).toLocaleString();
      item.append(text);
      if(job.download_url) {
        const link=document.createElement('a');link.textContent='تنزيل MP4';link.href=job.download_url;
        link.style.color='#eac884';link.setAttribute('download','');item.append(link);
      }
      if(job.state!=='rendering') {
        const button=document.createElement('button');button.type='button';button.textContent='حذف';
        button.addEventListener('click',async()=>{
          if(!window.confirm('حذف هذا الفيديو أو الطلب؟')) return;
          button.disabled=true;
          try { await videoFetch('/ai/videos/'+job.id,{method:'DELETE',headers:{'X-CSRF-Token':csrf}});await loadVideos(); }
          catch(error) { videoStatus.textContent=error.message;button.disabled=false; }
        });
        item.append(button);
      }
      list.append(item);
    }
  } catch(error) { videoStatus.textContent=error.message; }
}
videoBuilder.addEventListener('toggle',async()=>{
  if(!videoBuilder.open) return;
  loadVideos();
  if(videosInitialized) return;
  try {
    const data=await videoFetch('/products');
    for(const product of data.products.filter(p=>p.status==='ACTIVE')) {
      const option=document.createElement('option');option.value=product.id;option.textContent=product.title;
      videoProduct.append(option);
    }
    videosInitialized=true;
  } catch(error) { videoStatus.textContent=error.message; }
});
videoProduct.addEventListener('change',async()=>{
  const version=++videoSelectionVersion;
  const photos=document.getElementById('video-photos');photos.replaceChildren();
  createVideo.disabled=true;
  if(!videoProduct.value) return;
  videoStatus.textContent='جاري تحميل صور الفستان…';
  try {
    const data=await videoFetch('/ai/videos/product?id='+encodeURIComponent(videoProduct.value));
    if(version!==videoSelectionVersion) return;
    for(const [index,image] of data.product.images.nodes.entries()) {
      const label=document.createElement('label');label.style.width='110px';
      const picture=document.createElement('img');picture.src=image.url;picture.alt=image.altText || 'صورة الفستان '+(index+1);
      picture.width=100;picture.height=120;picture.style.objectFit='contain';
      const check=document.createElement('input');check.type='checkbox';check.value=image.id;
      check.checked=index<3;
      check.addEventListener('change',()=>{
        const count=photos.querySelectorAll('input:checked').length;
        if(count>5) {check.checked=false;videoStatus.textContent='اختاري خمس صور كحد أقصى.';}
        createVideo.disabled=videoBusy || !photos.querySelector('input:checked');
      });
      label.append(picture,check,document.createTextNode('اختيار'));photos.append(label);
    }
    createVideo.disabled=!photos.querySelector('input:checked') || videoBusy;
    videoStatus.textContent=data.product.images.nodes.length ? 'اختاري من صورة واحدة إلى خمس صور؛ حافظي على نفس اللون إذا بدك فيديو للون واحد.' : 'هذا المنتج لا يحتوي صورًا.';
  } catch(error) { if(version===videoSelectionVersion) videoStatus.textContent=error.message; }
});
createVideo.addEventListener('click',async()=>{
  if(videoBusy) return;
  videoBusy=true;createVideo.disabled=true;
  try {
    const ids=[...document.querySelectorAll('#video-photos input:checked')].map(i=>i.value);
    const data=await videoFetch('/ai/videos',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},
      body:JSON.stringify({product_id:videoProduct.value,image_ids:ids,include_price:document.getElementById('video-price').checked,include_voice:document.getElementById('video-voice').checked,languages:document.getElementById('video-language').value==='all'?['ar','en','ko']:[document.getElementById('video-language').value],narrations:Object.fromEntries(['ar','en','ko'].map(lang=>[lang,document.getElementById('video-narration-'+lang).value]))})});
    videoStatus.textContent='تم حفظ طلبات الفيديو: '+(Array.isArray(data.video_id)?data.video_id.join('، '):data.video_id)+'. سيظهر زر التنزيل بعد تجهيز الخدمة له.';
    await loadVideos();
  } catch(error) { videoStatus.textContent=error.message; }
  finally {videoBusy=false;createVideo.disabled=!document.querySelector('#video-photos input:checked');}
});
const prepBuilder=document.getElementById('product-preparer');
const prepSelect=document.getElementById('prep-product');
const prepStatus=document.getElementById('prep-status');
let prepLoaded=false,prepVersion=0,prepProduct=null,prepMedia=[];
function prepValue(id){return document.getElementById('prep-'+id).value;}
function priceInputs(){return {price:prepValue('price'),cost:prepValue('cost'),shipping:prepValue('shipping'),fee_percent:prepValue('fee'),fixed_fee:prepValue('fixed')};}
async function prepPost(path,body){return videoFetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body)});}
function priceText(r,currency){return 'السعر: '+r.sale_price+' '+currency+'\n'+(r.complete?'فرق بعد التكاليف المدخلة: '+r.estimated_profit+' ('+r.margin_percent+'٪)\nتعادل التكاليف عند: '+r.break_even+'\n':'')+r.message;}
function drawPrepMedia(){
 const root=document.getElementById('prep-media');root.replaceChildren();
 prepMedia.forEach((m,i)=>{
  const row=document.createElement('div');row.style.cssText='display:flex;align-items:center;gap:8px;margin:8px 0';
  if(m.image?.url){const img=document.createElement('img');img.src=m.image.url;img.alt=m.alt||'صورة المنتج';img.style.cssText='width:70px;height:85px;object-fit:contain';row.append(img);}
  const label=document.createElement('span');label.textContent=(i===0?'الصورة الرئيسية':String(i+1))+(m.mediaContentType!=='IMAGE'?' — '+m.mediaContentType:'');row.append(label);
  for(const [delta,name] of [[-1,'↑'],[1,'↓']]){const b=document.createElement('button');b.type='button';b.textContent=name;b.disabled=i+delta<0||i+delta>=prepMedia.length;b.addEventListener('click',()=>{[prepMedia[i],prepMedia[i+delta]]=[prepMedia[i+delta],prepMedia[i]];drawPrepMedia();});row.append(b);}
  root.append(row);
 });
}
async function loadPreparations(){
 try{
  const data=await videoFetch('/ai/product-preparations');const root=document.getElementById('prep-list');root.replaceChildren();
  for(const job of data.preparations){
   const p=job.proposal,before=job.before;const box=document.createElement('div');box.className='bubble agent';
   const states={pending:'بانتظار الموافقة',executing:'بدأ التنفيذ؛ إذا استمر راجعي Shopify ولا تكرريه',completed:'تم التنفيذ',needs_review:'تنفيذ جزئي أو غير مؤكد؛ راجعي Shopify قبل أي إعادة',failed:'لم يبدأ تعديل المنتج؛ جهزي اقتراحًا جديدًا',expired:'انتهت صلاحية الاقتراح',rejected:'مرفوض',reconciled:'تمت مراجعة النتيجة يدويًا؛ ليست شهادة نجاح آلي'};
   const copy=document.createElement('p');copy.textContent='تجهيز #'+job.id+' — '+(states[job.state]||job.state)+'\nمرحلة: '+job.stage+'\nقبل: '+before.title+'\nبعد: '+p.title+'\n'+p.description+'\nعنوان البحث: '+p.seo_title+'\nوصف البحث: '+p.seo_description+'\n'+priceText(p.price_review,before.currency)+'\nأسعار الخيارات الحالية: '+before.variants.nodes.map(v=>v.title+': '+v.price).join('، ')+'\nسعر جديد لكل الخيارات: '+p.price+'؛ إزالة أسعار المقارنة\nالنشر: '+(p.publication_name||'الحفاظ على الحالة الحالية: '+before.status)+'\nالمورّد: '+(p.supplier_url||'لم يحدد رابط')+'\nتأكيد المورّد من المالكة: '+(p.supplier_confirmed_by_owner?'نعم':'لا')+'؛ تحقق الوكيل المباشر: غير متاح';box.append(copy);
   const old=document.createElement('details');const summary=document.createElement('summary');summary.textContent='الوصف السابق للمقارنة';const content=document.createElement('p');content.textContent=before.descriptionHtml;old.append(summary,content);box.append(old);
   const gallery=document.createElement('div');gallery.style.cssText='display:flex;flex-wrap:wrap;gap:6px';
   for(const mid of p.media_order){const m=before.media.nodes.find(x=>x.id===mid);if(m?.image?.url){const img=document.createElement('img');img.src=m.image.url;img.alt=m.alt||'ترتيب الصورة المقترح';img.style.cssText='width:55px;height:70px;object-fit:contain';gallery.append(img);}}box.append(gallery);
   if(job.state==='pending')for(const [decision,label] of [['approve','موافقة وتنفيذ التعديلات'+(p.publication_id?' والنشر':'')],['reject','رفض']]){
    const btn=document.createElement('button');btn.type='button';btn.textContent=label;
    btn.addEventListener('click',async()=>{box.querySelectorAll('button').forEach(b=>b.disabled=true);try{const r=await prepPost('/ai/product-preparations/'+job.id+'/'+decision,{});prepStatus.textContent=states[r.state]||r.state;}catch(e){prepStatus.textContent=e.message;}await loadPreparations();});box.append(btn);
   }
   if(job.state==='needs_review'||job.state==='executing'){
    const check=document.createElement('input');check.type='checkbox';const label=document.createElement('label');label.append(check,document.createTextNode(' راجعت Shopify بنفسي وحسمت نتيجة هذا التنفيذ'));
    const btn=document.createElement('button');btn.type='button';btn.textContent='تسجيل انتهاء المراجعة فقط';btn.disabled=true;check.addEventListener('change',()=>btn.disabled=!check.checked);
    btn.addEventListener('click',async()=>{btn.disabled=true;try{await prepPost('/ai/product-preparations/'+job.id+'/reconcile',{confirmed:true});await loadPreparations();}catch(e){prepStatus.textContent=e.message;btn.disabled=false;}});box.append(label,btn);
   }
   root.append(box);
  }
 }catch(e){prepStatus.textContent=e.message;}
}
prepBuilder.addEventListener('toggle',async()=>{
 if(!prepBuilder.open)return;await loadPreparations();if(prepLoaded)return;
 try{const data=await videoFetch('/products');for(const p of data.products){const o=document.createElement('option');o.value=p.id;o.textContent=p.title+' — '+p.status;prepSelect.append(o);}prepLoaded=true;}catch(e){prepStatus.textContent=e.message;}
 try{const data=await videoFetch('/ai/product-preparations/publications');const s=document.getElementById('prep-publication');for(const p of data.publications){const o=document.createElement('option');o.value=p.id;o.textContent=p.name;s.append(o);}}catch(e){document.getElementById('prep-channel-note').textContent=e.message;}
});
prepSelect.addEventListener('change',async()=>{
 const version=++prepVersion;prepProduct=null;prepMedia=[];drawPrepMedia();
 if(!prepSelect.value)return;prepStatus.textContent='جاري قراءة الفستان…';
 try{const d=await videoFetch('/ai/product-preparations/product?id='+encodeURIComponent(prepSelect.value));if(version!==prepVersion)return;prepProduct=d.product;
 document.getElementById('prep-stock').textContent='عملة المتجر: '+prepProduct.currency+' — مخزون Shopify: '+prepProduct.variants.nodes.map(v=>v.title+': '+v.inventoryQuantity).join('، ')+'\n'+prepProduct.supplier_inventory.message;
 document.getElementById('prep-price').value=prepProduct.variants.nodes[0]?.price||'';
 document.getElementById('prep-title').value=prepProduct.title;
 const parsed=new DOMParser().parseFromString(prepProduct.descriptionHtml,'text/html');parsed.querySelectorAll('script,style').forEach(n=>n.remove());parsed.querySelectorAll('br').forEach(n=>n.replaceWith('\n'));parsed.querySelectorAll('td,th').forEach(n=>n.append(' | '));parsed.querySelectorAll('p,tr,li,h1,h2,h3').forEach(n=>n.append('\n'));document.getElementById('prep-description').value=parsed.body.textContent.trim();
 document.getElementById('prep-seo-title').value=prepProduct.seo?.title||'';document.getElementById('prep-seo-description').value=prepProduct.seo?.description||'';
 for(const id of ['cost','shipping','fee','fixed','supplier','notes'])document.getElementById('prep-'+id).value='';document.getElementById('prep-confirm').checked=false;document.getElementById('prep-publication').value='';document.getElementById('prep-price-result').textContent='';
 prepMedia=[...prepProduct.media.nodes];drawPrepMedia();prepStatus.textContent='الفستان جاهز للمراجعة؛ لم يتم تعديله.';
 }catch(e){if(version===prepVersion)prepStatus.textContent=e.message;}
});
document.getElementById('prep-review').addEventListener('click',async()=>{try{if(!prepProduct)throw new Error('اختاري الفستان أولًا.');const d=await prepPost('/ai/product-preparations/price',priceInputs());document.getElementById('prep-price-result').textContent=priceText(d.review,prepProduct.currency);}catch(e){prepStatus.textContent=e.message;}});
document.getElementById('prep-discuss').addEventListener('click',()=>{if(!prepProduct){prepStatus.textContent='اختاري الفستان أولًا.';return;}input.value='ناقش معي سعر هذا الفستان دون تنفيذ أي تعديل: '+prepProduct.title+'، المعرف '+prepProduct.id+'، العملة '+prepProduct.currency+'، المبالغ التي أدخلتها '+JSON.stringify(priceInputs())+'. اذكر التكاليف الناقصة ولا تفترض أنها صفر، وميّز الربح قبل الإعلان عن الربح الصافي.';input.focus();});
document.getElementById('prep-generate').addEventListener('click',async function(){const version=prepVersion;this.disabled=true;try{if(!prepProduct)throw new Error('اختاري الفستان أولًا.');const d=await prepPost('/ai/product-preparations/copy',{product_id:prepProduct.id,notes:prepValue('notes')});if(version!==prepVersion)return;for(const [key,id] of [['title','title'],['description','description'],['seo_title','seo-title'],['seo_description','seo-description']])document.getElementById('prep-'+id).value=d.copy[key];prepMedia=d.copy.media_order.map(id=>prepProduct.media.nodes.find(m=>m.id===id));drawPrepMedia();prepStatus.textContent='راجعي النصوص والمقاسات؛ لم يتم تعديل المنتج.';}catch(e){prepStatus.textContent=e.message;}finally{this.disabled=false;}});
document.getElementById('prep-save').addEventListener('click',async function(){this.disabled=true;try{if(!prepProduct)throw new Error('اختاري الفستان أولًا.');await prepPost('/ai/product-preparations',{product_id:prepProduct.id,proposal:{...priceInputs(),source_revision:prepProduct.revision,title:prepValue('title'),description:prepValue('description'),seo_title:prepValue('seo-title'),seo_description:prepValue('seo-description'),media_order:prepMedia.map(m=>m.id),publication_id:prepValue('publication'),supplier_url:prepValue('supplier'),supplier_confirmed_by_owner:document.getElementById('prep-confirm').checked}});prepStatus.textContent='حُفظت المعاينة أدناه؛ راجعيها ثم وافقي. لم يبدأ التنفيذ.';await loadPreparations();}catch(e){prepStatus.textContent=e.message;}finally{this.disabled=false;}});

const videoTimer=setInterval(loadVideos,5000);
window.addEventListener('pagehide',()=>clearInterval(videoTimer));

</script>
</body>
</html>
"""


@chat_ui.route("/assistant", methods=["GET"])
def assistant_page():
    return Response(PAGE.replace("{{ csrf_token() }}", csrf_token()), mimetype="text/html")
