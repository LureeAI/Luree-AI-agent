import os
import unittest
from unittest.mock import patch, MagicMock
os.environ['AGENT_PASSWORD'] = 'test-only-password-123'
os.environ['AGENT_SESSION_SECRET'] = 'test-only-session-secret-' + 'x'*32
os.environ['DATABASE_URL'] = 'postgresql://unused'
from app import app
import shopify_service
from agent_service import run_agent

class Phases(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def login(self):
        self.client.get('/login', base_url='https://localhost')
        with self.client.session_transaction() as session:
            token = session['csrf']
        with patch('access_control.login_allowed', return_value=True), patch('access_control.clear_login_failures'):
            response = self.client.post('/login', data={'csrf':token,'password':os.environ['AGENT_PASSWORD']},base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        with self.client.session_transaction() as session:
            return session['csrf']

    def test_private_routes_and_fail_closed(self):
        for path in ['/ai/history','/ai/memory','/products','/analyze','/shopify/products','/callback','/shopify/connect']:
            self.assertEqual(self.client.get(path).status_code,401,path)
        self.assertEqual(self.client.get('/assistant').status_code,302)
        self.assertEqual(self.client.get('/health').status_code,200)
        with patch.dict(app.config, {'AGENT_PASSWORD_HASH':''}):
            self.assertEqual(self.client.get('/assistant').status_code,503)

    def test_login_csrf_logout(self):
        csrf = self.login()
        self.assertEqual(self.client.post('/ai/chat',json={'message':'hi'}).status_code,403)
        with patch('agent_routes.run_agent',return_value={'success':True,'answer':'hi'}) as run:
            response=self.client.post('/ai/chat',json={'message':'hi'},headers={'X-CSRF-Token':csrf})
            self.assertEqual(response.status_code,200);run.assert_called_once_with('hi')
        self.assertEqual(self.client.post('/logout',headers={'X-CSRF-Token':csrf}).status_code,200)
        self.assertEqual(self.client.get('/ai/history').status_code,401)

    def test_login_rate_limit(self):
        self.client.get('/login')
        with self.client.session_transaction() as session: token=session['csrf']
        with patch('access_control.login_allowed',return_value=False):
            self.assertEqual(self.client.post('/login',data={'csrf':token,'password':'wrong'}).status_code,429)

    def test_pagination_and_bad_cursor(self):
        pages=[{'products':{'nodes':[{'id':'1'}],'pageInfo':{'hasNextPage':True,'endCursor':'next'}}},
               {'products':{'nodes':[{'id':'2'}],'pageInfo':{'hasNextPage':False,'endCursor':'last'}}}]
        with patch('shopify_service._graphql_request',side_effect=pages) as api:
            self.assertEqual([p['id'] for p in shopify_service.get_products()],['1','2'])
            self.assertEqual(api.call_args_list[1].args[1]['after'],'next')
        with patch('shopify_service._graphql_request',return_value=pages[0]):
            with self.assertRaises(RuntimeError):shopify_service.get_products()

    def test_coverage(self):
        with patch('shopify_service._graphql_request',return_value={'currentAppInstallation':{'accessScopes':[{'handle':'read_orders'}]}}),patch('shopify_service.get_products',return_value=[{}]*51),patch('shopify_service.get_orders',return_value=[]):
            data=shopify_service.get_store_context()
            self.assertEqual(data['product_count'],51)
            self.assertFalse(data['coverage']['all_order_history_permission'])
            self.assertIn('60 days',data['coverage']['orders'])

    def test_memory_used_and_success_saved(self):
        old=[{'role':'user','content':'remember budget'}]
        with patch('agent_service.load_messages',return_value=old),patch('agent_service.get_preferences',return_value='budget 5'),patch('agent_service.build_store_context',return_value='store'),patch('agent_service.ask_llm',return_value='answer') as model,patch('agent_service.save_exchange') as save:
            self.assertTrue(run_agent('question')['memory_saved'])
            model.assert_called_once_with('question','store',old,'budget 5')
            save.assert_called_once_with('question','answer')

    def test_api_memory_and_rendered_script(self):
        csrf=self.login()
        with patch('agent_routes.set_preferences') as save,patch('agent_routes.get_preferences',return_value='budget'):
            self.assertEqual(self.client.put('/ai/memory',json={'instructions':'budget'},headers={'X-CSRF-Token':csrf}).status_code,200)
            save.assert_called_once_with('budget')
        with patch('agent_routes.load_messages',return_value=[{'role':'user','content':'old'}]):
            self.assertEqual(self.client.get('/ai/history').json['messages'][0]['content'],'old')
        page=self.client.get('/assistant').data.decode()
        self.assertNotIn('{{ csrf_token() }}',page)
        from pathlib import Path
        Path('/tmp/luree-phase123.js').write_text(page.split('<script>')[1].split('</script>')[0])

if __name__ == '__main__':unittest.main()
