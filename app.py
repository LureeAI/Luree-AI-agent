import os
import time
import requests
from flask import Flask, jsonify

app = Flask(name)

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN")
SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY")
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET")

SHOPIFY_API_VERSION = "2026-07"

_token_cache = {
    "access_token": None,
    "expires_at": 0
}


def get_shop_domain():
    if not SHOPIFY_STORE_DOMAIN:
        return None

    domain = SHOPIFY_STORE_DOMAIN.strip()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.rstrip("/")

    return domain


def get_access_token():
    # Use cached token if it is still valid
    if (
        _token_cache["access_token"]
        and time.time() < _token_cache["expires_at"]
    ):
        return _token_cache["access_token"], None

    shop_domain = get_shop_domain()

    if not shop_domain:
        return None, "SHOPIFY_STORE_DOMAIN is missing"

    if not SHOPIFY_API_KEY:
        return None, "SHOPIFY_API_KEY is missing"

    if not SHOPIFY_API_SECRET:
        return None, "SHOPIFY_API_SECRET is missing"

    token_url = f"https://{shop_domain}/admin/oauth/access_token"

    try:
        response = requests.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": SHOPIFY_API_KEY,
                "client_secret": SHOPIFY_API_SECRET
            },
            timeout=30
        )

        if response.status_code != 200:
            return None, {
                "status_code": response.status_code,
                "shopify_response": response.text
            }

        data = response.json()

        access_token = data.get("access_token")
        expires_in = data.get("expires_in", 86399)

        if not access_token:
            return None, {
                "error": "Shopify did not return an access token",
                "shopify_response": data
            }

        # Refresh a little before actual expiration
        _token_cache["access_token"] = access_token
        _token_cache["expires_at"] = time.time() + expires_in - 300

        return access_token, None

    except Exception as e:
        return None, str(e)


def shopify_graphql(query, variables=None):
    access_token, token_error = get_access_token()

    if token_error:
        return None, token_error

    shop_domain = get_shop_domain()

    url = (
        f"https://{shop_domain}/admin/api/"
        f"{SHOPIFY_API_VERSION}/graphql.json"
    )

    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json={
                "query": query,
                "variables": variables or {}
            },
            timeout=30
        )

        if response.status_code != 200:
            return None, {
                "status_code": response.status_code,
                "shopify_response": response.text
            }

        data = response.json()

        if data.get("errors"):
            return None, data["errors"]

        return data.get("data"), None

    except Exception as e:
        return None, str(e)


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
    query = """
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

    data, error = shopify_graphql(query)

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
    query = """
    query AnalyzeProducts {
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
              title
              price
              inventoryQuantity
            }
          }
        }
      }
    }
    """

    data, error = shopify_graphql(query)

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
            try:
                prices.append(float(variant.get("price", 0)))
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
