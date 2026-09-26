import os
from flask import Blueprint, jsonify, request
from ai_analysis import analyze_products


ai_agent = Blueprint("ai_agent", name)


AGENT_NAME = "Luree AI Agent"
AGENT_VERSION = "1.0.0"


def build_agent_response(message, products=None):
    if message is None:
        message = ""

    message = str(message).strip()

    if products is None:
        products = []

    if not isinstance(products, list):
        products = []

    analysis = analyze_products(products)

    if not message:
        return {
            "success": True,
            "agent": AGENT_NAME,
            "message": "Luree AI Agent is ready.",
            "analysis": analysis
        }

    message_lower = message.lower()

    if (
        "product" in message_lower
        or "products" in message_lower
        or "منتج" in message
        or "منتجات" in message
    ):
        return {
            "success": True,
            "agent": AGENT_NAME,
            "message": "Product analysis completed.",
            "analysis": analysis
        }

    if (
        "inventory" in message_lower
        or "stock" in message_lower
        or "مخزون" in message
    ):
        return {
            "success": True,
            "agent": AGENT_NAME,
            "message": "Inventory analysis completed.",
            "analysis": {
                "total_inventory": analysis.get("total_inventory", 0),
                "average_inventory": analysis.get("average_inventory", 0),
                "out_of_stock_count": analysis.get(
                    "out_of_stock_count",
                    0
                ),
                "low_stock_count": analysis.get(
                    "low_stock_count",
                    0
                ),
                "high_stock_count": analysis.get(
                    "high_stock_count",
                    0
                ),
                "out_of_stock": analysis.get(
                    "out_of_stock",
                    []
                ),
                "low_stock": analysis.get(
                    "low_stock",
                    []
                )
            }
        }

    return {
        "success": True,
        "agent": AGENT_NAME,
        "message": (
            "I am ready to analyze Luree Fashions products, "
            "inventory, sales, and store performance."
        ),
        "analysis": analysis
    }


@ai_agent.route("/agent/health", methods=["GET"])
def agent_health():
    return jsonify({
        "success": True,
        "agent": AGENT_NAME,
        "version": AGENT_VERSION,
        "status": "ready"
    })


@ai_agent.route("/agent/chat", methods=["POST"])
def agent_chat():
    data = request.get_json(silent=True)

    if data is None:
        data = {}

    message = data.get("message", "")
    products = data.get("products", [])

    result = build_agent_response(
        message=message,
        products=products
    )

    return jsonify(result)
