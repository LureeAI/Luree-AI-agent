from flask import Blueprint, jsonify, request
from ai_agent import build_agent_response


chat = Blueprint("chat", name)


@chat.route("/chat/health", methods=["GET"])
def chat_health():
    return jsonify({
        "success": True,
        "service": "Luree AI Agent Chat",
        "status": "ready"
    })


@chat.route("/chat", methods=["POST"])
def chat_message():
    data = request.get_json(silent=True)

    if data is None:
        data = {}

    message = data.get("message", "")
    products = data.get("products", [])

    if not isinstance(message, str):
        message = str(message)

    if not isinstance(products, list):
        products = []

    result = build_agent_response(
        message=message,
        products=products
    )

    return jsonify(result)
