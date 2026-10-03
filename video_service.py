"""Durable job queue and MP4 outputs in standard PostgreSQL."""
import json
import re
import tempfile
from pathlib import Path
from database import _connect, store_key
from shopify_service import _graphql_request
from video_renderer import download_photo, render_video, MAX_VIDEO_BYTES
from video_audio import make_music, make_narration, mux_audio
from decimal import Decimal, InvalidOperation

LANGUAGE_NAMES={'ar':'Arabic','en':'English','ko':'Korean'}
DEFAULT_SCRIPTS={
    'ar':'اكتشفي فستانك المفضل مع لوري فاشن. تألقي بإطلالة جديدة، وشاهدي التفاصيل في متجرنا. تسوقي الآن.',
    'en':'Find your next favorite dress at Luree Fashions. Discover your new look and explore the details in our store. Shop now.',
    'ko':'루리 패션에서 마음에 드는 드레스를 만나보세요. 새로운 스타일을 발견하고 매장에서 자세히 확인하세요. 지금 쇼핑하세요.'}

class VideoError(RuntimeError):
    pass

def prepare(conn):
    conn.execute('SELECT pg_advisory_xact_lock(7432105)')
    conn.execute("""CREATE TABLE IF NOT EXISTS agent_videos (
        id BIGSERIAL PRIMARY KEY, shop TEXT NOT NULL, product_id TEXT NOT NULL,
        snapshot JSONB NOT NULL, state TEXT NOT NULL DEFAULT 'queued',
        video BYTEA, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ)""")
    conn.execute("CREATE INDEX IF NOT EXISTS agent_videos_shop_id ON agent_videos(shop,id)")

def product_video_details(product_id):
    if not isinstance(product_id,str) or not re.fullmatch(r'gid://shopify/Product/\d+',product_id):
        raise VideoError('اختاري منتجًا صحيحًا.')
    data=_graphql_request("""query($id:ID!){product(id:$id){id title status updatedAt
        priceRangeV2{minVariantPrice{amount currencyCode} maxVariantPrice{amount currencyCode}}
        images(first:30){nodes{id url altText}}}}""",{'id':product_id})
    p=data.get('product')
    if not p:
        raise VideoError('المنتج غير موجود.')
    return p

def create_video_job(product_id,image_ids,include_price,include_voice=False,narration='',language='en',languages=None,narrations=None):
    selected=languages if languages is not None else [language]
    if not isinstance(selected,list) or not 1<=len(selected)<=3 or any(not isinstance(x,str) or x not in LANGUAGE_NAMES for x in selected) or len(set(selected))!=len(selected):
        raise VideoError('اختاري العربية أو الإنكليزية أو الكورية.')
    scripts=narrations if narrations is not None else {language:narration}
    if not isinstance(scripts,dict) or any(k not in LANGUAGE_NAMES or not isinstance(v,str) or len(v)>300 or len(v.split())>40 for k,v in scripts.items()):
        raise VideoError('كل نص يجب ألا يتجاوز ٤٠ كلمة أو ٣٠٠ حرف.')
    if len(selected)>1 and not include_voice:
        raise VideoError('فعّلي التعليق الصوتي لإنشاء نسخ بلغات مختلفة.')
    if type(include_voice) is not bool or not isinstance(narration,str) or len(narration)>300 or len(narration.split())>40:
        raise VideoError('التعليق الصوتي يجب ألا يتجاوز ٤٠ كلمة أو ٣٠٠ حرف.')
    if include_voice:
        import os
        if not os.environ.get('OPENAI_API_KEY','').strip():
            raise VideoError('التعليق الصوتي يحتاج ربط OpenAI.')
    if type(include_price) is not bool or not isinstance(image_ids,list) or not 1<=len(image_ids)<=5 or any(not isinstance(i,str) for i in image_ids) or len(set(image_ids))!=len(image_ids):
        raise VideoError('اختاري من صورة واحدة إلى خمس صور مختلفة.')
    product=product_video_details(product_id)
    if product.get('status')!='ACTIVE':
        raise VideoError('اختاري منتجًا نشطًا قبل تجهيز إعلان.')
    images={p['id']:p for p in product['images']['nodes']}
    if any(i not in images for i in image_ids):
        raise VideoError('الصور المختارة لا تنتمي لهذا المنتج.')
    price=''
    if include_price:
        minimum=product['priceRangeV2']['minVariantPrice']
        maximum=product['priceRangeV2']['maxVariantPrice']
        try:
            amount=Decimal(minimum['amount'])
            high=Decimal(maximum['amount'])
            if not amount.is_finite() or amount<=0 or not high.is_finite() or high<amount:
                raise VideoError('سعر المنتج غير صالح للإعلان.')
        except (InvalidOperation,KeyError,TypeError):
            raise VideoError('تعذّر قراءة سعر المنتج.') from None
        price=('From ' if amount!=high else '')+format(amount,'f')+' '+minimum['currencyCode']
    snapshot={'title':product['title'],'price':price,'images':[images[i] for i in image_ids],
        'product_updated_at':product['updatedAt'],'include_price':include_price,
        'duration_seconds':15,'width':720,'height':1280,'audio':True,
        'include_voice':include_voice}
    with _connect() as conn:
        prepare(conn)
        count=conn.execute("SELECT COUNT(*) FROM agent_videos WHERE shop=%s",(store_key(),)).fetchone()[0]
        queued=conn.execute("SELECT COUNT(*) FROM agent_videos WHERE shop=%s AND state IN ('queued','rendering')",(store_key(),)).fetchone()[0]
        if count+len(selected)>10:
            raise VideoError('وصلتِ إلى عشرة فيديوهات؛ احذفي فيديو قديمًا لإضافة جديد.')
        if queued+len(selected)>3:
            raise VideoError('توجد ثلاثة فيديوهات قيد التجهيز؛ انتظري انتهاء أحدها.')
        ids=[]
        for lang in selected:
            localized=dict(snapshot,language=lang,narration=scripts.get(lang,'').strip() or DEFAULT_SCRIPTS[lang])
            row=conn.execute("""INSERT INTO agent_videos(shop,product_id,snapshot)
                VALUES (%s,%s,%s::jsonb) RETURNING id""",(store_key(),product_id,json.dumps(localized))).fetchone()
            ids.append(row[0])
    return ids if languages is not None else ids[0]

def list_videos():
    with _connect() as conn:
        prepare(conn)
        rows=conn.execute("""SELECT id,product_id,snapshot,state,created_at FROM agent_videos
            WHERE shop=%s ORDER BY id DESC LIMIT 10""",(store_key(),)).fetchall()
    return [dict(id=r[0],product_id=r[1],title=r[2]['title'],price=r[2]['price'],state=r[3],
        language=r[2].get('language','en'),created_at=r[4].isoformat(),duration_seconds=15,include_voice=r[2].get('include_voice',False),
        download_url=f'/ai/videos/{r[0]}/file' if r[3]=='ready' else None) for r in rows]

def get_video(aid):
    with _connect() as conn:
        prepare(conn)
        row=conn.execute("SELECT video FROM agent_videos WHERE shop=%s AND id=%s AND state='ready'",(store_key(),aid)).fetchone()
    return bytes(row[0]) if row else None

def delete_video(aid):
    with _connect() as conn:
        prepare(conn)
        # Active work must finish before deleting; prevents orphaned writes.
        return conn.execute("""DELETE FROM agent_videos WHERE shop=%s AND id=%s
            AND state IN ('queued','ready','failed') RETURNING id""",(store_key(),aid)).fetchone() is not None

def process_one_video():
    shop=store_key()
    if not shop:
        return False
    with _connect() as conn:
        prepare(conn)
        conn.execute("""UPDATE agent_videos SET state='failed',completed_at=NOW()
            WHERE shop=%s AND state='rendering' AND started_at < NOW()-INTERVAL '15 minutes'""",(shop,))
        row=conn.execute("""SELECT id,snapshot FROM agent_videos WHERE shop=%s AND state='queued'
            ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1""",(shop,)).fetchone()
        if not row:
            return False
        aid,snapshot=row
        conn.execute("UPDATE agent_videos SET state='rendering',started_at=NOW() WHERE id=%s",(aid,))
    try:
        with tempfile.TemporaryDirectory(prefix='luree-video-') as directory:
            photos=[download_photo(image['url']) for image in snapshot['images']]
            silent=render_video(photos,snapshot['title'],snapshot['price'],Path(directory)/'silent.mp4')
            music=make_music(Path(directory)/'music.wav')
            voice=make_narration(snapshot['narration'],Path(directory)/'voice.wav',snapshot.get('language','en')) if snapshot.get('include_voice') else None
            output=mux_audio(silent,music,voice,Path(directory)/'dress.mp4')
            if output.stat().st_size>MAX_VIDEO_BYTES:
                raise RuntimeError('Video is too large')
            video=output.read_bytes()
        with _connect() as conn:
            prepare(conn)
            conn.execute("""UPDATE agent_videos SET state='ready',video=%s,completed_at=NOW()
                WHERE id=%s AND shop=%s AND state='rendering'""",(video,aid,shop))
    except Exception:
        # No raw provider error/URL/credentials returned to the client.
        with _connect() as conn:
            prepare(conn)
            conn.execute("""UPDATE agent_videos SET state='failed',completed_at=NOW()
                WHERE id=%s AND shop=%s AND state='rendering'""",(aid,shop))
    return True

