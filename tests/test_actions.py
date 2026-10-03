import unittest
from unittest.mock import MagicMock, patch
import action_service as actions

class ActionTests(unittest.TestCase):
    def test_model_has_proposal_only(self):
        self.assertEqual(actions.PROPOSAL_TOOL['name'],'propose_action')
        self.assertNotIn('execute',actions.PROPOSAL_TOOL['parameters']['properties'])

    def test_stale_product_prevents_write(self):
        current={'id':'gid://shopify/Product/1','updatedAt':'new','handle':'dress'}
        with patch('action_service.current_product',return_value=current),patch('action_service.requests.post') as post:
            with self.assertRaises(actions.ActionError):
                actions._apply('product_title',current['id'],'New title',{'updatedAt':'old'})
            post.assert_not_called()

    def test_approved_description_is_escaped_and_handle_preserved(self):
        current={'id':'gid://shopify/Product/1','updatedAt':'same','handle':'dress'}
        response=MagicMock(status_code=200)
        response.json.return_value={'data':{'productUpdate':{'product':{'id':current['id']},'userErrors':[]}}}
        with patch('action_service.current_product',return_value=current),patch('action_service._get_connection',return_value=('test.myshopify.com','token')),patch('action_service.requests.post',return_value=response) as post:
            actions._apply('product_description',current['id'],'<script>bad</script>',current)
            product=post.call_args.kwargs['json']['variables']['product']
            self.assertEqual(product['handle'],'dress')
            self.assertNotIn('<script>',product['descriptionHtml'])

    def test_rejected_or_repeated_action_never_executes(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.return_value=('product_title','id','title',{},'pending',False)
        with patch('action_service._connect') as db,patch('action_service._apply') as apply:
            db.return_value.__enter__.return_value=conn
            self.assertEqual(actions.decide_action(1,'reject'),'rejected')
            apply.assert_not_called()
            conn.execute.return_value.fetchone.return_value=('product_title','id','title',{},'completed',False)
            with self.assertRaises(actions.ActionError):actions.decide_action(1,'approve')
            apply.assert_not_called()

    def test_transport_ambiguity_requires_review(self):
        conn=MagicMock()
        conn.execute.return_value.fetchone.return_value=('product_title','id','title',{},'pending',False)
        with patch('action_service._connect') as db,patch('action_service._apply',side_effect=TimeoutError):
            db.return_value.__enter__.return_value=conn
            self.assertEqual(actions.decide_action(1,'approve'),'needs_review')

    def test_private_execution_route(self):
        from app import app
        client=app.test_client()
        self.assertEqual(client.post('/ai/actions/1/approve').status_code,401)
        with client.session_transaction() as session: session['owner']=True;session['csrf']='csrf'
        self.assertEqual(client.post('/ai/actions/1/approve').status_code,403)
        with patch('action_service.decide_action',return_value='completed') as decide:
            self.assertEqual(client.post('/ai/actions/1/approve',headers={'X-CSRF-Token':'csrf'}).json['state'],'completed')
            decide.assert_called_once_with(1,'approve')

if __name__=='__main__':unittest.main()

