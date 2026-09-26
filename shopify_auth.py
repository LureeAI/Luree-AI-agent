import os
import hmac
import hashlib
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, redirect, request, jsonify

shopify_auth = Blueprint("shopify_auth", __name__)

SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "").strip()
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "").strip()
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip()

APP_URL = "https://luree-ai-agent-production.up.railway.app"

SCOPES = ",".join([
    "read_products",
    "read_inventory",
    "read_locations",
    "read_orders",
    "read_customers",
    "read_analytics"
])

oauth_state = None
shopify_access_token = None


def clean_shop_domain():
    domain = SHOPIFY_STORE_DOMAIN
    domain = domain.replace("https://", "")
    domain = domain.replace("http://", "")
    return domain.rstrip("/")


@shopify_auth.route("/shopify/connect")
def shopify_connect():
    global oauth_state

    oauth_state = secrets.token_urlsafe(32)

    shop = clean_shop_domain()

    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SCOPES,
        "redirect_uri": f"{APP_URL}/callback",
        "state": oauth_state
    }

    authorization_url = (
        f"https://{shop}/admin/oauth/authorize?"
        + urlencode(params)
    )

    return redirect(authorization_url)


@shopify_auth.route("/callback")
def shopify_callback():
    global shopify_access_token

    shop = request.args.get("shop")
    code = request.args.get("code")
    state = request.args.get("state")
    received_hmac = request.args.get("hmac")

    if not shop or not code or not state or not received_hmac:
        return jsonify({
            "success": False,
            "error": "Missing OAuth parameters"
        }), 400

    if state != oauth_state:
        return jsonify({
            "success": False,
            "error": "Invalid OAuth state"
        }), 400

    message = "&".join(
        f"{key}={value}"
        for key, value in sorted(request.args.items())
        if key != "hmac"
    )

    calculated_hmac = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hmac, received_hmac):
        return jsonify({
            "success": False,
            "error": "Invalid HMAC"
        }), 400

    token_url = f"https://{shop}/admin/oauth/access_token"

    response = requests.post(
        token_url,
        data={
            "client_id": SHOPIFY_API_KEY,
            "client_secret": SHOPIFY_API_SECRET,
            "code": code
        },
        timeout=30
    )

    if response.status_code != 200:
        return jsonify({
            "success": False,
            "error": "Token exchange failed",
            "status_code": response.status_code
        }), 400

    token_data = response.json()

    shopify_access_token = token_data.get("access_token")

    if not shopify_access_token:
        return jsonify({
            "success": False,
            "error": "Shopify did not return an access token"
        }), 400

    return jsonify({
        "success": True,
        "message": "Luree AI Agent connected to Shopify successfully",
        "shop": shop
    })
    
  @shopify_auth.route("/shopify/products")
def shopify_products():
    if not shopify_access_token:
        return jsonify({
            "success": False,
            "error": "Shopify is not connected"
        }), 401

    shop = clean_shop_domain()

    query = """
    query {
      products(first: 20) {
        nodes {
          id
          title
          status
          totalInventory
          productType
          vendor
        }
      }
    }
    """

    response = requests.post(
        f"https://{shop}/admin/api/2026-07/graphql.json",
        headers={
            "X-Shopify-Access-Token": shopify_access_token,
            "Content-Type": "application/json"
        },
        json={"query": query},
        timeout=30
    )

        return
    jsonify(response.json()),
    response.status_code
