import os
import time
import requests
from flask import Flask, jsonify
from shopify_auth import shopify_auth

app = Flask(__name__)
app.register_blueprint(shopify_auth)
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip()
SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "").strip()
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "").strip()

SHOPIFY_API_VERSION = "2026-07"

TOKEN_CACHE = {
    "access_token": None,
    "expires_at": 0
}


def clean_shop_domain():
    domain = SHOPIFY_STORE_DOMAIN
    domain = domain.replace("https://", "")
    domain = domain.replace("http://", "")
    domain = domain.rstrip("/")
    return domain


def get_access_token():
    if (
        TOKEN_CACHE["access_token"]
        and time.time() < TOKEN_CACHE["expires_at"]
    ):
        return TOKEN_CACHE["access_token"], None

    domain = clean_shop_domain()

    if not domain:
        return None, "SHOPIFY_STORE_DOMAIN is missing"

    if not SHOPIFY_API_KEY:
        return None, "SHOPIFY_API_KEY is missing"

    if not SHOPIFY_API_SECRET:
        return None, "SHOPIFY_API_SECRET is missing"

    url = f"https://{domain}/admin/oauth/access_token"

    try:
        response = requests.post(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": SHOPIFY_API_KEY,
                "client_secret": SHOPIFY_API_SECRET
            },
            headers={
                "Accept": "application/json"
            },
            timeout=30
        )
    except requests.RequestException as exc:
        return None, {
            "type": "connection_error",
            "message": str(exc)
        }

    if response.status_code != 200:
        return None, {
            "type": "token_error",
            "status_code": response.status_code,
            "shopify_response": response.text
        }

    try:
        token_data = response.json()
    except ValueError:
        return None, {
            "type": "token_error",
            "message": "Shopify returned invalid JSON",
            "shopify_response": response.text
        }

    access_token = token_data.get("access_token")

    if not access_token:
        return None, {
            "type": "token_error",
            "message": "No access token returned by Shopify",
            "shopify_response": token_data
        }

    expires_in = token_data.get("expires_in", 86400)

    try:
        expires_in = int(expires_in)
    except (TypeError, ValueError):
        expires_in = 86400

    TOKEN_CACHE["access_token"] = access_token
    TOKEN_CACHE["expires_at"] = (
        time.time() + max(expires_in - 300, 60)
    )

    return access_token, None


def shopify_graphql(query, variables=None):
    access_token, token_error = get_access_token()

    if token_error:
        return None, token_error

    domain = clean_shop_domain()

    url = (
        f"https://{domain}/admin/api/"
        f"{SHOPIFY_API_VERSION}/graphql.json"
    )

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
        "Accept": "application/json"
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
        return None, {
            "type": "connection_error",
            "message": str(exc)
        }

    if response.status_code != 200:
        return None, {
            "type": "graphql_http_error",
            "status_code": response.status_code,
            "shopify_response": response.text
        }

    try:
        result = response.json()
    except ValueError:
        return None, {
            "type": "graphql_error",
            "message": "Shopify returned invalid JSON",
            "shopify_response": response.text
        }

    if result.get("errors"):
        return None, {
            "type": "graphql_error",
            "errors": result["errors"]
        }

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
        "success": True,
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
