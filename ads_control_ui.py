"""Owner-only operational page. Secrets never enter the browser."""
from flask import render_template_string

PAGE = r'''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>إدارة إعلانات لوري</title>
<style>body{background:#10131b;color:#f0f0f3;font:17px Arial;max-width:850px;margin:auto;padding:24px}a{color:#eccb87}section{background:#222634;padding:22px;margin:18px 0;border-radius:16px}label{display:block;margin:12px 0}input,select,button{font:inherit;padding:10px;border-radius:7px;max-width:100%;box-sizing:border-box}input,select{display:block;width:100%}button{background:#eccb87;border:0;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px Arial}#message{white-space:pre-wrap}small{line-height:1.6}table{width:100%;text-align:right}td,th{padding:8px;border-bottom:1px solid #555}</style>
<a href="/assistant">الرجوع للوكيل</a><h1>إدارة إعلانات لوري</h1>
<section><h2>القدرات الحالية</h2><p>مراقبة حملات Meta الموجودة، وسجل القرارات، وإيقاف تلقائي اختياري عند بلوغ الحدود أو انتهاء التفويض. إطلاق الحملات وتعديل الميزانيات وإدارة تيك توك تلقائيًا لم تُنفّذ بعد.</p><p>حدود المراقبة ليست ضمانًا لسقف صرف لحظي: تقارير Meta تتأخر، وقد تنقطع الخدمة. اضبطي حدود الإنفاق ومدة الحملة داخل Meta أيضًا. التنبيهات هنا داخل اللوحة؛ لا توجد رسائل خارجية بعد.</p><p id="health">جاري قراءة الحالة…</p><button id="refresh">تحديث الحالة</button></section>
<section><h2>تفويض حملة موجودة</h2><form id="mandate">
<label>معرف حملة Meta<input name="campaign_id" required pattern="[0-9]{1,40}"></label>
<label>عملة حساب الإعلانات<input name="currency" required pattern="[A-Z]{3}" placeholder="USD أو KRW"></label>
<label>حد صرف يومي للحملة<input name="daily_limit" required type="number" min="0.01" step="any"></label>
<label>حد إجمالي للحملة خلال التفويض<input name="total_limit" required type="number" min="0.01" step="any"></label>
<label>انتهاء التفويض بتوقيت جهازك<input name="expiry" type="datetime-local" required></label>
<label>الصلاحية<select name="mode"><option value="observe">مراقبة وتسجيل فقط</option><option value="auto_pause">السماح بإيقاف هذه الحملة تلقائيًا حسب الحدود</option></select></label>
<p><small>يشمل الحساب الصرف منذ بداية يوم إضافة الحملة بتوقيت حساب Meta، وليس منذ لحظة الضغط. تعديل التفويض لا يصفر الصرف. الإيقاف تلقائيًا لا يعيد تشغيل الحملة ولا يزيد ميزانيتها.</small></p>
<button>حفظ تفويض الحملة</button></form><p id="message" role="status"></p></section>
<section><h2>التفويضات</h2><div id="policies"></div></section><section><h2>آخر القرارات والتنبيهات</h2><div id="events"></div></section>
<script>
const csrf={{ csrf_token()|tojson }};
async function api(path,method='GET',body){const r=await fetch(path,{method,headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok||!d.success)throw Error(d.error||'تعذر الطلب');return d;}
async function refresh(){try{const d=(await api('/ai/marketing/control')).control;document.getElementById('health').textContent=(d.live_pause_enabled?'مفتاح الإيقاف التلقائي متاح؛ ينفذ فقط للحملات المفوضة.':'وضع الاختبار: مفتاح التنفيذ التلقائي غير مفعّل.')+' '+(d.health?d.health.message+' آخر فحص: '+new Date(d.health.checked_at).toLocaleString():'لم تُسجّل دورة مراقبة بعد.');
if(d.health && Date.now()-new Date(d.health.checked_at).getTime()>600000)document.getElementById('health').textContent+=' تنبيه: المراقبة متأخرة؛ افحصي الحملات مباشرة في Meta.';
const p=document.getElementById('policies');p.replaceChildren();for(const m of d.mandates){const row=document.createElement('p');row.textContent=m.policy.campaign_name+' — '+m.campaign_id+' — '+(m.enabled?m.policy.mode:'ملغى')+' — '+m.policy.currency+' يومي '+m.policy.daily_limit+' / إجمالي '+m.policy.total_limit+' ';if(m.enabled){const b=document.createElement('button');b.textContent='إلغاء التفويض';b.onclick=async()=>{try{await api('/ai/marketing/control/'+m.campaign_id+'/revoke','POST',{});refresh();}catch(e){document.getElementById('message').textContent=e.message;}};row.append(b);}p.append(row);}
const out=document.getElementById('events');out.replaceChildren();for(const e of d.events){const row=document.createElement('pre');row.textContent=new Date(e.created_at).toLocaleString()+' | '+e.campaign_id+' | '+e.reason+' | '+e.state+'\n'+JSON.stringify(e.evidence,null,2);out.append(row);}
}catch(e){document.getElementById('health').textContent='تعذرت قراءة حالة المراقبة. تحققي من Meta مباشرةً. '+e.message;}}
document.getElementById('refresh').onclick=refresh;
document.getElementById('mandate').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const f=Object.fromEntries(new FormData(e.target));f.expires_at=new Date(f.expiry).toISOString();delete f.expiry;await api('/ai/marketing/control','PUT',f);document.getElementById('message').textContent='تم حفظ التفويض. راجعي حالة التنفيذ وآخر فحص أعلاه.';await refresh();}catch(err){document.getElementById('message').textContent=err.message;}finally{b.disabled=false;}};refresh();
</script></html>'''

def render_control():
    return render_template_string(PAGE)
