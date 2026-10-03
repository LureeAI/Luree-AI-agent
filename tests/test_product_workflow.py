import copy
import unittest
from unittest.mock import MagicMock, patch
import product_workflow as w

PRODUCT = {'id':'gid://shopify/Product/1','title':'Dress','descriptionHtml':'<p>Black dress</p>',
 'handle':'dress','status':'DRAFT','updatedAt':'2026-01-01','currency':'USD','revision':'revision',
 'seo':{'title':'','description':''},'options':[{'name':'Size','values':['M']}],
 'variants':{'nodes':[{'id':'gid://shopify/ProductVariant/1','price':'25.00','compareAtPrice':'40.00',
 'sku':'supplier-sku','title':'M','selectedOptions':[{'name':'Size','value':'M'}],
 'inventoryQuantity':12,'inventoryItem':{'id':'gid://shopify/InventoryItem/1','tracked':True}}], 'pageInfo':{'hasNextPage':False}},
 'media':{'nodes':[{'id':'gid://shopify/MediaImage/1','mediaContentType':'IMAGE','alt':'','image':{'url':'https://cdn.shopify.com/a.jpg'}}], 'pageInfo':{'hasNextPage':False}}}
PROPOSAL={'title':'New dress','description':'Black dress <script>','seo_title':'Dress','seo_description':'Black dress',
 'price':'30','cost':'10','shipping':'5','fee_percent':'3','fixed_fee':'1','source_revision':'revision'}

class PreparationTests(unittest.TestCase):
 def db(self,row):
  db=patch('product_workflow._connect');self.addCleanup(db.stop);mock=db.start();conn=MagicMock();mock.return_value.__enter__.return_value=conn
  conn.execute.return_value.fetchone.return_value=row
  return conn

 def test_price_calculation_and_missing_costs(self):
  r=w.price_review('30','10','5','3','1')
  self.assertEqual(r['estimated_profit'],'13.10');self.assertEqual(r['margin_percent'],'43.67')
  self.assertFalse(w.price_review('30','10','',None,'1')['complete'])
  for value in ('NaN','Infinity','-1','0.001',True):
   with self.assertRaises(w.PreparationError):w.price_review(value)
  with self.assertRaises(w.PreparationError):w.price_review('30','10','0','100','0')

 def test_foreign_media_and_stale_preview_blocked(self):
  for patch_data in ({'media_order':['foreign']},{'source_revision':'old'}):
   with self.assertRaises(w.PreparationError):w.validate(PRODUCT,{**PROPOSAL,**patch_data})

 def test_supplier_confirmation_and_costs_required_for_publish(self):
  with patch('product_workflow.publications',return_value=[{'id':'channel','name':'Online Store'}]):
   for extras in ({},{'supplier_confirmed_by_owner':True,'cost':''}):
    with self.assertRaises(w.PreparationError):w.validate(PRODUCT,{**PROPOSAL,'publication_id':'channel',**extras})
   r=w.validate(PRODUCT,{**PROPOSAL,'publication_id':'channel','supplier_confirmed_by_owner':True})
   self.assertFalse(r['supplier_inventory_verified_by_agent'])
   self.assertEqual(r['publication_name'],'Online Store')

 def test_product_pagination_never_silently_partial(self):
  p=copy.deepcopy(PRODUCT);p['variants']['pageInfo']['hasNextPage']=True
  with patch('product_workflow._graphql_request',return_value={'shop':{'currencyCode':'USD'},'product':p}):
   with self.assertRaises(w.PreparationError):w.details(p['id'])

 def test_changed_stock_blocks_before_write(self):
  p=copy.deepcopy(PRODUCT);p['variants']['nodes'][0]['inventoryQuantity']=9
  self.claim_db(w.validate(PRODUCT,PROPOSAL))
  with patch('product_workflow.details',return_value=p),patch('product_workflow.mutation') as mutate:
   self.assertEqual(w.decide(1,'approve'),'failed');mutate.assert_not_called()

 def test_repeated_approval_never_writes(self):
  self.db((PRODUCT['id'],PRODUCT,{},'executing',False))
  with patch('product_workflow.mutation') as mutate:
   with self.assertRaises(w.PreparationError):w.decide(1,'approve')
   mutate.assert_not_called()

 def claim_db(self,proposal):
  conn=self.db(None)
  def execute(query,*args):
   result=MagicMock()
   if 'SELECT target,before_data' in query:
    result.fetchone.return_value=(PRODUCT['id'],PRODUCT,proposal,'pending',False)
   else:result.fetchone.return_value=None
   return result
  conn.execute.side_effect=execute
  return conn

 def test_completed_keeps_supplier_identifiers_and_no_inventory_writes(self):
  p=w.validate(PRODUCT,PROPOSAL);self.claim_db(p)
  after=copy.deepcopy(PRODUCT);after['title']=p['title'];after['variants']['nodes'][0]['price']='30.00';after['variants']['nodes'][0]['compareAtPrice']=None
  with patch('product_workflow.details',side_effect=[PRODUCT,after]),patch('product_workflow._graphql_request',return_value={'currentAppInstallation':{'accessScopes':[{'handle':'write_products'}]}}),patch('product_workflow.mutation',return_value={'ok':True}) as mutate:
   self.assertEqual(w.decide(1,'approve'),'completed')
   variants=mutate.call_args_list[0].args[1]['variants']
   self.assertEqual(variants,[{'id':'gid://shopify/ProductVariant/1','price':'30.00','compareAtPrice':None}])
   product=mutate.call_args_list[1].args[1]['product']
   self.assertEqual(product['handle'],'dress');self.assertNotIn('<script>',product['descriptionHtml'])
   self.assertNotIn('status',product)

 def test_partial_failure_never_publishes_or_retries(self):
  p=w.validate(PRODUCT,PROPOSAL);self.claim_db(p)
  with patch('product_workflow.details',return_value=PRODUCT),patch('product_workflow._graphql_request',return_value={'currentAppInstallation':{'accessScopes':[{'handle':'write_products'}]}}),patch('product_workflow.mutation',side_effect=[{'ok':True},TimeoutError]) as mutate:
   self.assertEqual(w.decide(1,'approve'),'needs_review');self.assertEqual(mutate.call_count,2)

 def test_mutation_transport_has_no_retry(self):
  with patch('product_workflow._get_connection',return_value=('test.myshopify.com','token')),patch('product_workflow.requests.post',side_effect=TimeoutError) as post:
   with self.assertRaises(TimeoutError):w.mutation('query',{},'payload','product')
   post.assert_called_once();self.assertFalse(post.call_args.kwargs['allow_redirects'])

 def test_reconcile_does_not_write_shopify(self):
  self.db(('executing',False))
  with patch('product_workflow.mutation') as mutate:
   with self.assertRaises(w.PreparationError):w.reconcile(1,True)
   mutate.assert_not_called()

 def test_private_routes_and_csrf(self):
  from app import app
  c=app.test_client()
  self.assertEqual(c.get('/ai/product-preparations').status_code,401)
  with c.session_transaction() as s:s['owner']=True;s['csrf']='csrf'
  for path in ('','/copy','/price','/1/approve','/1/reconcile'):
   self.assertEqual(c.post('/ai/product-preparations'+path,json={}).status_code,403)
  with patch('product_workflow.price_review',return_value={'complete':False}):
   self.assertEqual(c.post('/ai/product-preparations/price',json={'price':'30'},headers={'X-CSRF-Token':'csrf'}).status_code,200)


 def test_publication_occurs_only_after_verified_edits(self):
  with patch('product_workflow.publications',return_value=[{'id':'channel','name':'Online Store'}]):
   p=w.validate(PRODUCT,{**PROPOSAL,'publication_id':'channel','supplier_confirmed_by_owner':True})
   self.claim_db(p)
   after=copy.deepcopy(PRODUCT);after['title']=p['title'];after['variants']['nodes'][0]['price']='30.00';after['variants']['nodes'][0]['compareAtPrice']=None
   with patch('product_workflow.details',side_effect=[PRODUCT,after]),patch('product_workflow._graphql_request',return_value={'currentAppInstallation':{'accessScopes':[{'handle':'write_products'},{'handle':'write_publications'}]}}),patch('product_workflow.mutation',side_effect=[{'ok':True},{'ok':True},{'ok':True},{'publishable':{'publishedOnPublication':True}}]) as mutate:
    self.assertEqual(w.decide(1,'approve'),'completed')
    self.assertEqual(mutate.call_count,4)
    self.assertEqual(mutate.call_args_list[2].args[1],{'product':{'id':PRODUCT['id'],'status':'ACTIVE'}})
    self.assertEqual(mutate.call_args_list[3].args[1]['input'],[{'publicationId':'channel'}])

 def test_missing_write_scope_stops_before_mutation(self):
  self.claim_db(w.validate(PRODUCT,PROPOSAL))
  with patch('product_workflow.details',return_value=PRODUCT),patch('product_workflow._graphql_request',return_value={'currentAppInstallation':{'accessScopes':[]}}),patch('product_workflow.mutation') as mutate:
   self.assertEqual(w.decide(1,'approve'),'failed');mutate.assert_not_called()

 def test_claim_is_committed_before_network_mutation(self):
  p=w.validate(PRODUCT,PROPOSAL)
  conn=self.claim_db(p)
  context=w._connect.return_value
  def mutate(*args):
   self.assertGreaterEqual(context.__exit__.call_count,1)
   claim=[c for c in conn.execute.call_args_list if 'UPDATE agent_product_preparations SET state=%s,stage=%s,' in c.args[0]]
   self.assertTrue(claim)
   self.assertEqual(claim[0].args[1][0],'executing')
   raise TimeoutError
  with patch('product_workflow.details',return_value=PRODUCT),patch('product_workflow._graphql_request',return_value={'currentAppInstallation':{'accessScopes':[{'handle':'write_products'}]}}),patch('product_workflow.mutation',side_effect=mutate):
   self.assertEqual(w.decide(1,'approve'),'needs_review')


 def test_copy_only_sends_trusted_photos_and_validates_order(self):
  import json
  client=MagicMock();client.with_options.return_value=client;client.responses.create.return_value.output_text=json.dumps({'title':'Dress','description':'Black dress','seo_title':'Dress','seo_description':'Black dress','media_order':['gid://shopify/MediaImage/1']})
  with patch('llm_service.get_client',return_value=client):
   result=w.generate_copy(PRODUCT,'Keep measurements')
  self.assertEqual(result['media_order'],['gid://shopify/MediaImage/1'])
  inputs=client.responses.create.call_args.kwargs['input'][0]['content']
  self.assertEqual([i['image_url'] for i in inputs if i['type']=='input_image'],['https://cdn.shopify.com/a.jpg'])
  p=copy.deepcopy(PRODUCT);p['media']['nodes'][0]['image']['url']='https://external.example/photo.jpg'
  with patch('llm_service.get_client',return_value=client):w.generate_copy(p)
  self.assertFalse(any(i['type']=='input_image' for i in client.responses.create.call_args.kwargs['input'][0]['content']))

 def test_generated_foreign_media_order_is_rejected(self):
  import json
  client=MagicMock();client.with_options.return_value=client;client.responses.create.return_value.output_text=json.dumps({'title':'Dress','description':'Black dress','seo_title':'Dress','seo_description':'Black dress','media_order':['foreign']})
  with patch('llm_service.get_client',return_value=client):
   with self.assertRaises(w.PreparationError):w.generate_copy(PRODUCT)


 def test_media_reorder_waits_for_job_before_verification(self):
  before=copy.deepcopy(PRODUCT);before['media']['nodes'].append({'id':'gid://shopify/MediaImage/2','mediaContentType':'IMAGE','alt':'','image':{'url':'https://cdn.shopify.com/b.jpg'}})
  p=w.validate(before,{**PROPOSAL,'media_order':['gid://shopify/MediaImage/2','gid://shopify/MediaImage/1']})
  conn=self.db(None)
  def execute(query,*args):
   r=MagicMock();r.fetchone.return_value=(before['id'],before,p,'pending',False) if 'SELECT target,before_data' in query else None
   return r
  conn.execute.side_effect=execute
  after=copy.deepcopy(before);after['media']['nodes'].reverse();after['title']=p['title'];after['variants']['nodes'][0]['price']='30.00';after['variants']['nodes'][0]['compareAtPrice']=None
  def read(query,*args):
   if 'currentAppInstallation' in query:return {'currentAppInstallation':{'accessScopes':[{'handle':'write_products'}]}}
   self.assertIn('job(id:$id)',query)
   return {'job':{'done':True}}
  with patch('product_workflow.details',side_effect=[before,after]),patch('product_workflow._graphql_request',side_effect=read),patch('product_workflow.mutation',side_effect=[{'ok':True},{'ok':True},{'job':{'id':'job'}}]) as mutate:
   self.assertEqual(w.decide(1,'approve'),'completed');self.assertEqual(mutate.call_count,3)

if __name__=='__main__':unittest.main()
