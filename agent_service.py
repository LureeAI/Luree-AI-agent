import json

from llm_service import ask_llm
from shopify_service import get_store_context


def build_store_context():
    store_data = get_store_context()

    return json.dumps(
        store_data,
        ensure_ascii=False,
        indent=2,
        default=str,
    )


def run_agent(message):
    if message is None:
        message = ""

    message = str(message).strip()

    if not message:
        return {
            "success": False,
            "error": "Message is required",
        }

    try:
        store_context = build_store_context()

        answer = ask_llm(
            message=message,
            store_context=store_context,
        )

        return {
            "success": True,
            "agent": "Luree AI Agent",
            "answer": answer,
        }

    except RuntimeError as error:
        return {
            "success": False,
            "error": str(error),
        }

    except Exception as error:
        return {
            "success": False,
            "error": "Agent request failed",
            "details": str(error),
        }
