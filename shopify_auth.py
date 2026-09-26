import os
import hmac
import hashlib
import secrets
from urllib.parse import urlencode

import requests
from flask import Blueprint, redirect, request, jsonify

shopify_auth = Blueprint("shopify_auth", name)

SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "").strip()
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "").strip()
SHOPIFY_STORE_DOMAIN = os.environ.get("SHOPIFY_STORE_DOMAIN", "").strip()

APP_URL = "https://luree-ai-agent-production.up.railway.app"
API_VERSION = "2026-04"

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
connected_shop = None


def clean_shop_domain(domain=None):
    domain = domain or SHOPIFY_STORE_DOMAIN
    domain = domain.replace("https://", "")
    domain = domain.replace("http://", "")
    return domain.rstrip("/")


@shopify_auth.route("/shopify/connect")
def shopify_connect():
    global oauth_state

    shop = clean_shop_domain()

    if not shop:
        return jsonify({
            "success": False,
            "error": "
