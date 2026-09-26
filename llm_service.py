import os

from openai import OpenAI


OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.5")


def get_client():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    return OpenAI(api_key=OPENAI_API_KEY)


def ask_llm(message, store_context=None):
    if not message:
        raise ValueError("Message is required")

    instructions = (
        "You are Luree AI Agent, an AI assistant for the Luree Fashions "
        "Shopify store. Analyze store information carefully and provide "
        "clear, practical recommendations. Focus on products, inventory, "
        "pricing, sales, marketing, and ecommerce performance. "
        "Do not invent store data that was not provided."
    )

    user_input = message

    if store_context:
        user_input = (
            f"STORE DATA:\n{store_context}\n\n"
            f"USER REQUEST:\n{message}"
        )

    client = get_client()

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=instructions,
        input=user_input
    )

    return response.output_text
