from flask import Blueprint, jsonify, request

from agent_service import run_agent


agent_routes = Blueprint(
    "agent_routes",
    __name__,
)

@agent_routes.route(
    "/ai/health",
    methods=["GET"],
)
def ai_health():
    return jsonify({
        "success": True,
        "agent": "Luree AI Agent",
        "status": "ready",
    })


@agent_routes.route(
    "/ai/chat",
    methods=["POST"],
)
def ai_chat():
    data = request.get_json(silent=True)

    if data is None:
        data = {}

    message = data.get("message", "")

    if not isinstance(message, str):
        message = str(message)

    message = message.strip()

    if not message:
        return jsonify({
            "success": False,
            "error": "Message is required",
        }), 400

    result = run_agent(message)

    if result.get("success"):
        return jsonify(result), 200

    return jsonify(result), 500
