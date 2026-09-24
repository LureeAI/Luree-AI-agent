import os
import requests
from flask import Flask, jsonify

app = Flask(__name__)

SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN")
SHOPIFY_API_VERSION = "2026-07"


def shopify_request(endpoint):
    url = (
        f"https://{SHOPIFY_STORE_DOMAIN}/admin/api/"
        f"{SHOPIFY_API_VERSION}/{endpoint}"
    )

    headers = {
        "X-Shopify-Access-Token": SHOPIFY_ACCESS_TOKEN,
        "Content-Type": "application/json"
    }

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code != 200:
        return None, {
            "status_code": response.status_code,
            "error": response.text
        }

    return response.json(), None


@app.route("/")
def home():
    return jsonify({
        "name": "Luree AI Agent",
        "status": "running",
        "store": SHOPIFY_STORE_DOMAIN,
        "shopify_configured": bool(
            SHOPIFY_STORE_DOMAIN and SHOPIFY_ACCESS_TOKEN
        ),
        "products_endpoint": "/products",
        "analysis_endpoint": "/analyze"
    })


@app.route("/products")
def products():
    data, error = shopify_request("products.json?limit=250")

    if error:
        return jsonify(error), 500

    products_list = data.get("products", [])

    results = []

    for product in products_list:
        variants = product.get("variants", [])

        prices = []
        inventory = 0

        for variant in variants:
            try:
                prices.append(float(variant.get("price", 0)))
            except (ValueError, TypeError):
                pass

            inventory += variant.get("inventory_quantity", 0) or 0

        results.append({
            "id": product.get("id"),
            "title": product.get("title"),
            "status": product.get("status"),
            "product_type": product.get("product_type"),
            "vendor": product.get("vendor"),
            "variants": len(variants),
            "inventory": inventory,
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0
        })

    return jsonify({
        "total_products": len(results),
        "products": results
    })


@app.route("/analyze")
def analyze():
    data, error = shopify_request("products.json?limit=250")

    if error:
        return jsonify(error), 500

    products_list = data.get("products", [])

    active = 0
    draft = 0
    out_of_stock = 0
    total_inventory = 0
    product_results = []

    for product in products_list:
        status = product.get("status")

        if status == "active":
            active += 1
        elif status == "draft":
            draft += 1

        variants = product.get("variants", [])

        inventory = sum(
            (variant.get("inventory_quantity", 0) or 0)
            for variant in variants
        )

        total_inventory += inventory

        if inventory <= 0:
            out_of_stock += 1

        prices = []

        for variant in variants:
            try:
                prices.append(float(variant.get("price", 0)))
            except (ValueError, TypeError):
                pass

        product_results.append({
            "title": product.get("title"),
            "status": status,
            "inventory": inventory,
            "variants": len(variants),
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0
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
