import json
import logging
from llm_service import ask_llm
from shopify_service import get_store_context
from database import load_messages, get_preferences, save_exchange


def build_store_context():
    context = json.dumps(get_store_context(), ensure_ascii=False, default=str)
    if len(context) > 250000:
        raise RuntimeError('Store context requires bulk analysis')
    return context


def run_agent(message):
    try:
        history = load_messages(20)
        preferences = get_preferences()
        store_context = build_store_context()
        answer = ask_llm(message, store_context, history, preferences)
        if not answer or not answer.strip():
            raise RuntimeError('Empty model response')
        save_exchange(message, answer)
        return {'success': True, 'agent': 'Luree AI Agent', 'answer': answer, 'memory_saved': True}
    except Exception:
        logging.exception('Agent request failed')
        return {'success': False, 'error': 'تعذّر إكمال الطلب أو حفظ المحادثة. جرّبي مجددًا.'}
