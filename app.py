import os

from flask import Flask, jsonify

app = Flask(__name__)

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN")
SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET")

@app.route("/")
def home():
    return jsonify({
        "name": "Luree AI Agent",
        "status": "running",
        "store": SHOPIFY_STORE_DOMAIN,
        "shopify_configured": bool(
            SHOPIFY_STORE_DOMAIN and
            SHOPIFY_API_KEY and
            SHOPIFY_API_SECRET
        )
    })

if __ name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
