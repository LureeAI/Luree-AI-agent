"""Owner-reviewed, persisted actions. Execution is never callable by the model."""
import html
import json
import os
import re
import requests
from database import _connect, store_key
from shopify_service import _graphql_request, _get_connection, API_VERSION
from ads_service import _json_get, AdsError

class ActionError(RuntimeError):
    pass

def prepare(conn):
    conn.execute('SELECT pg_advisory_xact_lock(7432104)')
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_actions (
        id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, kind TEXT NOT NULL,
        target TEXT NOT NULL, content TEXT NOT NULL, reason TEXT NOT NULL,
        before_data JSONB NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), completed_at TIMESTAMPTZ)""")

def current_product(target):
    data = _graphql_request('query($id:ID!){ product(id:$id){id title descriptionHtml handle updatedAt} }',{'id':target})
    product = data.get('product')
    if not product:
        raise ActionError('المنتج غير موجود.')
    return product

def current_campaign(target):
    from ads_service import configuration
    if not configuration()['meta']['configured'] or not target.isdigit():
        raise ActionError('يلزم ربط حساب Meta الصحيح.')
    version = os.environ['META_API_VERSION']
    if not re.fullmatch(r'v\d+\.\d+',version):
        raise ActionError('إصدار Meta غير صحيح.')
    campaign = _json_get(f'https://graph.facebook.com/{version}/{target}',
        {'Authorization':'Bearer '+os.environ['META_ACCESS_TOKEN']},
        {'fields':'id,name,account_id,status,updated_time'})
    account = os.environ['META_AD_ACCOUNT_ID'].removeprefix('act_').strip()
    if str(campaign.get('account_id')) != account or not campaign.get('status'):
        raise ActionError('الحملة لا تنتمي إلى حساب المتجر المربوط.')
    return campaign

def propose_action(kind, target, content, reason):
    if kind not in ('product_title','product_description','meta_pause'):
        raise ActionError('هذا النوع من التنفيذ غير متاح بعد.')
    if not all(isinstance(v,str) for v in (target,content,reason)):
        raise ActionError('بيانات الإجراء غير صحيحة.')
    if not reason.strip() or len(reason)>1000 or not content.strip() or len(content)>6000:
        raise ActionError('النص أو سبب الإجراء غير صحيح.')
    if kind == 'product_title' and len(content)>255:
        raise ActionError('عنوان المنتج طويل.')
    if kind.startswith('product_'):
        if not re.fullmatch(r'gid://shopify/Product/\d+',target):
            raise ActionError('يلزم معرّف منتج صحيح.')
        before = current_product(target)
    else:
        if content != 'PAUSED':
            raise ActionError('المتاح فقط إيقاف الحملة.')
        before = current_campaign(target)
    with _connect() as conn:
        prepare(conn)
        row=conn.execute("""INSERT INTO agent_actions(shop,kind,target,content,reason,before_data)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb) RETURNING id""",
            (store_key(),kind,target,content,reason,json.dumps(before))).fetchone()
    return {'action_id':row[0],'state':'pending','message':'اقتراح محفوظ ينتظر موافقة غصون؛ لم يتم تنفيذه.'}

def list_actions():
    with _connect() as conn:
        prepare(conn)
        rows=conn.execute("""SELECT id,kind,target,content,reason,before_data,state,created_at
            FROM agent_actions WHERE shop=%s ORDER BY id DESC LIMIT 50""",(store_key(),)).fetchall()
    return [dict(id=r[0],kind=r[1],target=r[2],content=r[3],reason=r[4],before=r[5],
        state=r[6],created_at=r[7].isoformat()) for r in rows]

def _apply(kind,target,content,before):
    if kind.startswith('product_'):
        current=current_product(target)
        if current['updatedAt'] != before.get('updatedAt'):
            raise ActionError('تغيّر المنتج بعد الاقتراح؛ اطلبي اقتراحًا جديدًا.')
        product={'id':target,'handle':current['handle']}
        if kind == 'product_title':
            product['title']=content
        else:
            product['descriptionHtml']='<p>'+html.escape(content).replace('\n','<br>')+'</p>'
        # Single attempt: transport ambiguity is surfaced and never auto-retried.
        shop,token=_get_connection()
        response=requests.post(f'https://{shop}/admin/api/{API_VERSION}/graphql.json',
            headers={'X-Shopify-Access-Token':token,'Content-Type':'application/json'},
            json={'query':'mutation($product:ProductUpdateInput!){ productUpdate(product:$product){ product{id} userErrors{field message} } }',
                'variables':{'product':product}},timeout=20,allow_redirects=False)
        data=response.json()
        payload=(data.get('data') or {}).get('productUpdate') or {}
        if response.status_code != 200 or data.get('errors') or payload.get('userErrors') or not payload.get('product'):
            raise ActionError('رفض Shopify التعديل؛ تحققي من صلاحية write_products.')
    elif kind == 'meta_pause':
        current=current_campaign(target)
        if current.get('updated_time') != before.get('updated_time') or current.get('status') != before.get('status'):
            raise ActionError('تغيّرت الحملة؛ اطلبي اقتراحًا جديدًا.')
        response=requests.post(f"https://graph.facebook.com/{os.environ['META_API_VERSION']}/{target}",
            headers={'Authorization':'Bearer '+os.environ['META_ACCESS_TOKEN']},
            data={'status':'PAUSED'},timeout=20,allow_redirects=False)
        if response.status_code != 200 or response.json().get('success') is not True:
            raise ActionError('رفض Meta الإيقاف؛ يلزم ads_management.')
    else:
        raise ActionError('نوع إجراء غير مسموح.')

def decide_action(aid, decision):
    if decision not in ('approve','reject'):
        raise ActionError('القرار غير صحيح.')
    with _connect() as conn:
        prepare(conn)
        row=conn.execute("""SELECT kind,target,content,before_data,state,
            created_at < NOW() - INTERVAL '24 hours'
            FROM agent_actions WHERE id=%s AND shop=%s FOR UPDATE""",(aid,store_key())).fetchone()
        if not row or row[4] != 'pending':
            raise ActionError('الإجراء غير موجود أو حُسم سابقًا.')
        if decision == 'reject':
            state='rejected'
        elif row[5]:
            state='expired'
        else:
            try:
                _apply(*row[:4])
                state='completed'
            except ActionError:
                state='failed'
            except Exception:
                # May have reached the provider: require human reconciliation, never resend.
                state='needs_review'
        conn.execute("UPDATE agent_actions SET state=%s,completed_at=NOW() WHERE id=%s AND shop=%s",
            (state,aid,store_key()))
    return state

PROPOSAL_TOOL = {
    'type':'function','name':'propose_action',
    'description':'Save a specific product title/description change or Meta campaign pause for owner review. Never executes. Use only when owner asks for a change and data provides a real target ID.',
    'parameters':{'type':'object','properties':{
        'kind':{'type':'string','enum':['product_title','product_description','meta_pause']},
        'target':{'type':'string'},'content':{'type':'string'},
        'reason':{'type':'string'}},
        'required':['kind','target','content','reason'],'additionalProperties':False},
    'strict':True}

