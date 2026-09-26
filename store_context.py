import json

from shopify_service import get_store_context


def load_store_data():
    try:
        data = get_store_context()

        if not isinstance(data, dict):
            return {
                "success": False,
                "error": "Invalid Shopify store data",
            }

        return {
            "success": True,
            "data": data,
        }

    except Exception as error:
        return {
            "success": False,
            "error": str(error),
        }


def build_store_prompt():
    result = load_store_data()

    if not result.get("success"):
        raise RuntimeError(
            result.get(
                "error",
                "Could not load Shopify store data",
            )
        )

    store_data = result.get("data", {})

    return json.dumps(
        store_data,
        ensure_ascii=False,
        indent=2,
        default=str,
    )
