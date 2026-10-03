import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from PIL import Image
import video_service as videos
from video_renderer import download_photo, render_video, compose

PRODUCT={'id':'gid://shopify/Product/1','title':'Black Satin Dress','status':'ACTIVE','updatedAt':'now',
    'priceRangeV2':{'minVariantPrice':{'amount':'49.00','currencyCode':'USD'},'maxVariantPrice':{'amount':'59.00','currencyCode':'USD'}},
    'images':{'nodes':[{'id':'gid://shopify/ProductImage/1','url':'https://cdn.shopify.com/a.jpg','altText':'Black dress'}]}}

class VideoTests(unittest.TestCase):
    def test_arbitrary_urls_rejected_before_network(self):
        for url in ['http://cdn.shopify.com/a.jpg','https://127.0.0.1/a.jpg','https://cdn.shopify.com.evil.com/a.jpg',
            'https://user:pass@cdn.shopify.com/a.jpg','https://cdn.shopify.com:8443/a.jpg']:
            with patch('video_renderer.requests.get') as get:
                with self.assertRaises(ValueError):download_photo(url)
                get.assert_not_called()

    def test_invalid_selection_and_foreign_images_never_queue(self):
        for ids in [[],['x']*6,['x','x'],[{}]]:
            with self.assertRaises(videos.VideoError):videos.create_video_job(PRODUCT['id'],ids,True)
        with patch('video_service.product_video_details',return_value=PRODUCT),patch('video_service._connect') as db:
            with self.assertRaises(videos.VideoError):videos.create_video_job(PRODUCT['id'],['foreign-image'],True)
            db.assert_not_called()

    def test_price_range_snapshot_and_no_fake_single_price(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.side_effect=[(0,),(0,),(7,)]
        with patch('video_service.product_video_details',return_value=PRODUCT),patch('video_service._connect') as db:
            db.return_value.__enter__.return_value=conn
            self.assertEqual(videos.create_video_job(PRODUCT['id'],[PRODUCT['images']['nodes'][0]['id']],True),7)
        import json
        insert=[c for c in conn.execute.call_args_list if 'INSERT INTO agent_videos(' in c.args[0]][0]
        snapshot=json.loads(insert.args[1][2])
        self.assertEqual(snapshot['price'],'From 49.00 USD')
        self.assertTrue(snapshot['audio'])
        self.assertFalse(snapshot['include_voice'])
        self.assertEqual(snapshot['duration_seconds'],15)

    def test_three_languages_queued_with_native_scripts(self):
        import json
        conn=MagicMock()
        conn.execute.return_value.fetchone.side_effect=[(0,),(0,),(11,),(12,),(13,)]
        with patch('video_service.product_video_details',return_value=PRODUCT),patch('video_service._connect') as db,patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}):
            db.return_value.__enter__.return_value=conn
            ids=videos.create_video_job(PRODUCT['id'],[PRODUCT['images']['nodes'][0]['id']],True,True,languages=['ar','en','ko'])
        self.assertEqual(ids,[11,12,13])
        snapshots=[json.loads(c.args[1][2]) for c in conn.execute.call_args_list if 'INSERT INTO agent_videos(' in c.args[0]]
        self.assertEqual([s['language'] for s in snapshots],['ar','en','ko'])
        for s in snapshots:
            self.assertEqual(s['narration'],videos.DEFAULT_SCRIPTS[s['language']])
            self.assertEqual(s['images'],snapshots[0]['images'])

    def test_batch_quota_rejects_before_any_insert(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.side_effect=[(8,),(0,)]
        with patch('video_service.product_video_details',return_value=PRODUCT),patch('video_service._connect') as db,patch.dict(os.environ,{'OPENAI_API_KEY':'test-only'}):
            db.return_value.__enter__.return_value=conn
            with self.assertRaises(videos.VideoError):
                videos.create_video_job(PRODUCT['id'],[PRODUCT['images']['nodes'][0]['id']],True,True,languages=['ar','en','ko'])
        self.assertFalse(any('INSERT INTO' in c.args[0] for c in conn.execute.call_args_list))

    def test_quota_prevents_unbounded_video_storage(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.side_effect=[(10,),(0,)]
        with patch('video_service.product_video_details',return_value=PRODUCT),patch('video_service._connect') as db:
            db.return_value.__enter__.return_value=conn
            with self.assertRaises(videos.VideoError):videos.create_video_job(PRODUCT['id'],[PRODUCT['images']['nodes'][0]['id']],False)

    def test_failed_render_is_persisted_not_ready(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.return_value=(1,{'images':[{'url':'https://cdn.shopify.com/a.jpg'}],'title':'Dress','price':''})
        with patch('video_service._connect') as db,patch('video_service.download_photo',side_effect=ValueError('bad image')):
            db.return_value.__enter__.return_value=conn
            with patch.dict(os.environ,{'SHOPIFY_STORE_DOMAIN':'test.myshopify.com'}):
                self.assertTrue(videos.process_one_video())
        sql=[c.args[0] for c in conn.execute.call_args_list]
        self.assertTrue(any("SET state='failed',completed_at" in s for s in sql))
        self.assertFalse(any("SET state='ready'" in s for s in sql))

    def test_private_routes_and_video_range_download(self):
        from app import app
        client=app.test_client()
        for path in ['/ai/videos','/ai/videos/product','/ai/videos/1/file']:
            self.assertEqual(client.get(path).status_code,401)
        with client.session_transaction() as session:session['owner']=True;session['csrf']='csrf'
        self.assertEqual(client.post('/ai/videos',json={}).status_code,403)
        self.assertEqual(client.delete('/ai/videos/1').status_code,403)
        with patch('video_service.get_video',return_value=b'1234567890'):
            response=client.get('/ai/videos/1/file',headers={'Range':'bytes=0-3'})
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,b'1234')
            self.assertEqual(response.headers['Cache-Control'],'no-store')
        with patch('video_service.create_video_job',return_value=1):
            self.assertEqual(client.post('/ai/videos',json={'product_id':PRODUCT['id'],'image_ids':['1']},headers={'X-CSRF-Token':'csrf'}).status_code,202)

    def test_entire_garment_is_contained(self):
        photo=Image.new('RGB',(100,400),'white')
        from PIL import ImageDraw
        d=ImageDraw.Draw(photo);d.rectangle((20,0,80,399),fill='red')
        frame=compose(photo,0,'Dress','49 USD')
        self.assertEqual(frame.size,(720,1280))
        # Garment top/bottom remain inside photo area with no cut-off crop.
        self.assertEqual(frame.getpixel((360,150)),(255,0,0))
        self.assertEqual(frame.getpixel((360,998)),(255,0,0))

if __name__=='__main__':unittest.main()

