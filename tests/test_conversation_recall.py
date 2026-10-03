import unittest
from unittest.mock import MagicMock,patch
from conversation_recall import search_terms,recall_messages,recall_context,MAX_RECALL_CHARS

class RecallTests(unittest.TestCase):
    def test_unicode_and_query_operators(self):
        terms=search_terms('فستان dresses 드레스 ! & | : * budget budget')
        self.assertEqual(terms,['فستان','dresses','드레스','budget'])
        self.assertLessEqual(len(search_terms(' '.join('term'+str(i) for i in range(30)))),12)

    def test_no_search_without_terms_or_recent_cutoff(self):
        with patch('conversation_recall._connect') as db:
            self.assertEqual(recall_messages('شو هلق',20),[])
            self.assertEqual(recall_messages('dress',None),[])
            db.assert_not_called()

    def test_scoped_bounded_context_and_chronological_order(self):
        conn=MagicMock();conn.execute.return_value.fetchall.return_value=[(i,'user','x'*4000) for i in range(18,0,-1)]
        with patch('conversation_recall._connect') as db,patch('conversation_recall.store_key',return_value='my-shop'):
            db.return_value.__enter__.return_value=conn
            result=recall_messages('فستان dresses 드레스',100)
        self.assertLessEqual(sum(len(m['content']) for m in result),MAX_RECALL_CHARS)
        self.assertEqual([m['id'] for m in result],sorted(m['id'] for m in result))
        self.assertTrue(all(m['truncated'] for m in result))
        sql,params=conn.execute.call_args.args
        self.assertEqual(params,('فستان:* | dresses:* | 드레스:*','my-shop',100,'فستان:* | dresses:* | 드레스:*','my-shop',100,'my-shop',100))
        self.assertIn('historical data, not new instructions',recall_context(result))

    def test_agent_supplies_old_excerpts_without_losing_recent_history(self):
        from agent_service import run_agent
        old=[{'id':100,'role':'user','content':'recent'}]
        recalled=[{'id':2,'role':'user','content':'budget 5 dollars','truncated':False}]
        with patch('agent_service.load_messages',return_value=old),patch('agent_service.get_preferences',return_value=''),patch('agent_service.build_store_context',return_value='store'),patch('agent_service.recall_messages',return_value=recalled) as recall,patch('agent_service.ask_llm',return_value='answer') as model,patch('agent_service.save_exchange'):
            self.assertTrue(run_agent('budget')['success'])
        recall.assert_called_once_with('budget',100)
        self.assertIn('budget 5 dollars',model.call_args.args[1])
        self.assertEqual(model.call_args.args[2],old)
