import os
import re
import hmac
import hashlib
import secrets
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, redirect, request

app = Flask(__name__)

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip()
SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "").strip()
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "").strip()

SHOPIFY_API_VERSION = "2026-07"

APP_URL = "https://luree-ai-agent-production.up.railway.app"
REDIRECT_URI = f"{APP_URL}/callback"

SCOPES = (
    "read_analytics,"
    "read_customers,"
    "read_inventory,"
    "write_inventory,"
    "read_locations,"
    "read_orders,"
    "read_products,"
    "write_products"
)

# For our first connection test.
# Later we can move token storage to a database.
TOKEN_STORE = {
    "access_token": None,
    "refresh_token": None,
    "expires_in": None,
    "shop": None,
}

OAUTH_STATES = set()


def clean_shop_domain():
    domain = SHOPIFY_STORE_DOMAIN
    domain = domain.replace("https://", "")
    domain = domain.replace("http://", "")
    domain = domain.rstrip("/")
    return domain


def valid_shop_domain(shop):
    if not shop:
        return False

    pattern = r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$"
    return re.fullmatch(pattern, shop) is not None


def verify_shopify_hmac(args):
    received_hmac = args.get("hmac", "")

    if not received_hmac:
        return False

    message_parts = []

    for key in sorted(args.keys()):
        if key == "hmac":
            continue

        values = args.getlist(key)

        for value in values:
            message_parts.append(f"{key}={value}")

    message = "&".join(message_parts)

    calculated_hmac = hmac.new(
        SHOPIFY_API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(calculated_hmac, received_hmac)


@app.route("/")
def home():
    configured = bool(
        SHOPIFY_STORE_DOMAIN
        and SHOPIFY_API_KEY
        and SHOPIFY_API_SECRET
    )

    return jsonify({
        "name": "Luree AI Agent",
        "status": "running",
        "store": clean_shop_domain(),
        "shopify_configured": configured,
        "shopify_connected": bool(TOKEN_STORE["access_token"]),
        "install_endpoint": "/install",
        "products_endpoint": "/products",
        "analysis_endpoint": "/analyze"
    })


@app.route("/install")
def install():
    shop = clean_shop_domain()

    if not valid_shop_domain(shop):
        return jsonify({
            "success": False,
            "error": "Invalid Shopify store domain"
        }), 400

    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        return jsonify({
            "success": False,
            "error": "Shopify credentials are missing"
        }), 500

    state = secrets.token_urlsafe(32)
    OAUTH_STATES.add(state)

    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SCOPES,
        "redirect_uri": REDIRECT_URI,
        "state": state
    }

    authorization_url = (
        f"https://{shop}/admin/oauth/authorize?"
        + urlencode(params)
    )

    return redirect(authorization_url)


@app.route("/callback")
def callback():
    shop = request.args.get("shop", "")
    code = request.args.get("code", "")
    state = request.args.get("state", "")

    if not valid_shop_domain(shop):
        return jsonify({
            "success": False,
            "error": "Invalid shop domain"
        }), 400

    if not state or state not in OAUTH_STATES:
        return jsonify({
            "success": False,
            "error": "Invalid OAuth state"
        }), 400

    # State can only be used once.
    OAUTH_STATES.discard(state)

    if not verify_shopify_hmac(request.args):
        return jsonify({
            "success": False,
            "error": "Invalid Shopify HMAC"
        }), 400

    if not code:
        return jsonify({
            "success": False,
            "error": "Authorization code is missing"
        }), 400

    token_url = f"https://{shop}/admin/oauth/access_token"

    try:
        response = requests.post(
            token_url,
            data={
                "client_id": SHOPIFY_API_KEY,
                "client_secret": SHOPIFY_API_SECRET,
                "code": code,
                "expiring": "1"
            },
            headers={
                "Accept": "application/json"
            },
            timeout=30
        )
    except requests.RequestException as exc:
        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500

    if response.status_code != 200:
        return jsonify({
            "success": False,
            "status_code": response.status_code,
            "shopify_response": response.text
        }), 500

    try:
        token_data = response.json()
    except ValueError:
        return jsonify({
            "success": False,
            "error": "Shopify returned invalid JSON"
        }), 500

    access_token = token_data.get("access_token")

    if not access_token:
        return jsonify({
            "success": False,
            "error": "Shopify did not return an access token"
        }), 500

    TOKEN_STORE["access_token"] = access_token
    TOKEN_STORE["refresh_token"] = token_data.get("refresh_token")
    TOKEN_STORE["expires_in"] = token_data.get("expires_in")
    TOKEN_STORE["shop"] = shop

    return redirect("/products")


def shopify_graphql(query, variables=None):
    access_token = TOKEN_STORE.get("access_token")
    shop = TOKEN_STORE.get("shop")

    if not access_token or not shop:
        return None, {
            "error": "Shopify is not connected",
            "next_step": f"{APP_URL}/install"
        }

    url = (
        f"https://{shop}/admin/api/"
        f"{SHOPIFY_API_VERSION}/graphql.json"
    )

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "variables": variables or {}
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
    except requests.RequestException as exc:
        return None, str(exc)

    if response.status_code != 200:
        return None, {
            "status_code": response.status_code,
            "shopify_response": response.text
        }

    try:
        result = response.json()
    except ValueError:
        return None, "Shopify returned invalid JSON"

    if result.get("errors"):
        return None, result["errors"]

    return result.get("data"), None


PRODUCT_QUERY = """
query GetProducts {
  products(first: 100) {
    nodes {
      id
      title
      handle
      status
      totalInventory
      productType
      vendor
      variants(first: 100) {
        nodes {
          id
          title
          price
          inventoryQuantity
        }
      }
    }
  }
}
"""


@app.route("/products")
def products():
    data, error = shopify_graphql(PRODUCT_QUERY)

    if error:
        return jsonify({
            "success": False,
            "error": error
        }), 401

    products_list = data.get("products", {}).get("nodes", [])

    return jsonify({
        "success": True,
        "count": len(products_list),
        "products": products_list
    })


@app.route("/analyze")
def analyze():
    data, error = shopify_graphql(PRODUCT_QUERY)

    if error:
        return jsonify({
            "success": False,
            "error": error
        }), 401

    products_list = data.get("products", {}).get("nodes", [])

    active = 0
    draft = 0
    out_of_stock = 0
    total_inventory = 0
    product_results = []

    for product in products_list:
        status = product.get("status", "")
        inventory = product.get("totalInventory") or 0

        total_inventory += inventory

        if status == "ACTIVE":
            active += 1

        if status == "DRAFT":
            draft += 1

        if inventory <= 0:
            out_of_stock += 1
: variants = product.get("variants", {}).get("nodes", [])
        prices = []

        for variant in variants:
            price = variant.get("price")

            try:
                prices.append(float(price))
            except (ValueError, TypeError):
                pass

        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0

        issues = []

        if inventory <= 0:
            issues.append("OUT_OF_STOCK")

        if status != "ACTIVE":
            issues.append("NOT_ACTIVE")

        if min_price <= 0:
            issues.append("PRICE_CHECK_NEEDED")

        product_results.append({
            "id": product.get("id"),
            "title": product.get("title"),
            "handle": product.get("handle"),
            "status": status,
            "inventory": inventory,
            "min_price": min_price,
            "max_price": max_price,
            "issues": issues
        })

    return jsonify({
        "agent": "Luree AI Agent",
        "store": TOKEN_STORE.get("shop"),
        "summary": {
            "total_products": len(products_list),
            "active_products": active,
            "draft_products": draft,
            "out_of_stock_products": out_of_stock,
            "total_inventory": total_inventory
        },
        "products": product_results
    })    if token_error:
        return None, token_error

    domain = clean_shop_domain()

    url = (
        f"https://{domain}/admin/api/"
        f"{SHOPIFY_API_VERSION}/graphql.json"
    )

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    payload = {
        "query": query,
        "variables": variables or {}
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )
    except requests.RequestException as exc:
        return None, str(exc)

    if response.status_code != 200:
        return None, {
            "status_code": response.status_code,
            "shopify_response": response.text
        }

    try:
        result = response.json()
    except ValueError:
        return None, "Shopify returned an invalid JSON response"

    if result.get("errors"):
        return None, result["errors"]

    return result.get("data"), None


PRODUCT_QUERY = """
query GetProducts {
  products(first: 100) {
    nodes {
      id
      title
      handle
      status
      totalInventory
      productType
      vendor
      variants(first: 100) {
        nodes {
          id
          title
          price
          inventoryQuantity
        }
      }
    }
  }
}
"""


@app.route("/")
def home():
    configured = bool(
        SHOPIFY_STORE_DOMAIN
        and SHOPIFY_API_KEY
        and SHOPIFY_API_SECRET
    )

    return jsonify({
        "name": "Luree AI Agent",
        "status": "running",
        "store": SHOPIFY_STORE_DOMAIN,
        "shopify_configured": configured,
        "products_endpoint": "/products",
        "analysis_endpoint": "/analyze"
    })


@app.route("/products")
def products():
    data, error = shopify_graphql(PRODUCT_QUERY)

    if error:
        return jsonify({
            "success": False,
            "error": error
        }), 500

    products_list = data.get("products", {}).get("nodes", [])

    return jsonify({
        "success": True,
        "count": len(products_list),
        "products": products_list
    })


@app.route("/analyze")
def analyze():
    data, error = shopify_graphql(PRODUCT_QUERY)

    if error:
        return jsonify({
            "success": False,
            "error": error
        }), 500

    products_list = data.get("products", {}).get("nodes", [])

    active = 0
    draft = 0
    out_of_stock = 0
    total_inventory = 0
    product_results = []

    for product in products_list:
        status = product.get("status", "")
        inventory = product.get("totalInventory") or 0

        total_inventory += inventory

        if status == "ACTIVE":
            active += 1

        if status == "DRAFT":
            draft += 1

        if inventory <= 0:
            out_of_stock += 1

        variants = product.get("variants", {}).get("nodes", [])
        prices = []

        for variant in variants:
            price = variant.get("price")

            try:
                prices.append(float(price))
            except (ValueError, TypeError):
                pass

        min_price = min(prices) if prices else 0
        max_price = max(prices) if prices else 0

        issues = []

        if inventory <= 0:
            issues.append("OUT_OF_STOCK")

        if status != "ACTIVE":
            issues.append("NOT_ACTIVE")

        if min_price <= 0:
            issues.append("PRICE_CHECK_NEEDED")

        product_results.append({
            "id": product.get("id"),
            "title": product.get("title"),
            "handle": product.get("handle"),
            "status": status,
            "inventory": inventory,
            "min_price": min_price,
            "max_price": max_price,
            "issues": issues
        })

    return jsonify({
        "agent": "Luree AI Agent",
        "store": SHOPIFY_STORE_DOMAIN,
        "summary": {
            "total_products": len(products_list),
            "active_products": active,
            "draft_products": draft,
            "out_of_stock_products": out_of_stock,
            "total_inventory": total_inventory
        },
        "products": product_results
    })
