import os
import time
from datetime import datetime, timezone
import requests
from database import load_shopify_connection
import shopify_auth as shopify_module

API_VERSION = os.environ.get('SHOPIFY_API_VERSION', '2026-04')


def _get_connection():
    shop, token = load_shopify_connection()
    shop = shop or shopify_module.connected_shop
    token = token or shopify_module.shopify_access_token
    if not shop or not token:
        raise RuntimeError('Shopify is not connected')
    return shop, token


def _graphql_request(query, variables=None):
    shop, token = _get_connection()
    for attempt in range(4):
        response = requests.post(f'https://{shop}/admin/api/{API_VERSION}/graphql.json',
            headers={'X-Shopify-Access-Token':token, 'Content-Type':'application/json'},
            json={'query':query,'variables':variables or {}}, timeout=20)
        if response.status_code == 429 and attempt < 3:
            time.sleep(min(2 ** attempt, 4))
            continue
        response.raise_for_status()
        result = response.json()
        errors = result.get('errors', [])
        if errors and all(e.get('extensions', {}).get('code') == 'THROTTLED' for e in errors) and attempt < 3:
            time.sleep(min(2 ** attempt, 4))
            continue
        if errors or not isinstance(result.get('data'), dict):
            raise RuntimeError('Shopify could not return complete data')
        return result['data']
    raise RuntimeError('Shopify rate limit')


PRODUCT_FIELDS = '''id title handle status vendor productType totalInventory createdAt updatedAt
priceRangeV2 { minVariantPrice { amount currencyCode } maxVariantPrice { amount currencyCode } }'''
ORDER_FIELDS = '''id name createdAt displayFinancialStatus displayFulfillmentStatus
 totalPriceSet { shopMoney { amount currencyCode } }'''


def _paginate(resource, fields, limit=None):
    # Never silently return the first page or claim a partial download is complete.
    nodes, cursor, seen = [], None, set()
    deadline = time.monotonic() + 90
    extra = ', sortKey: CREATED_AT, reverse: true' if resource == 'orders' else ', sortKey: ID'
    query = ('query Page($first:Int!, $after:String) { ' + resource +
             '(first:$first, after:$after' + extra + ') { nodes { ' + fields +
             ' } pageInfo { hasNextPage endCursor } } }')
    while True:
        if time.monotonic() > deadline or len(nodes) >= 25000:
            raise RuntimeError('Store is too large for synchronous reading; bulk sync is required')
        size = min(100, limit - len(nodes)) if limit else 100
        data = _graphql_request(query, {'first':size, 'after':cursor})
        connection = data.get(resource)
        if not isinstance(connection, dict) or 'pageInfo' not in connection or 'nodes' not in connection:
            raise RuntimeError('Missing pagination metadata')
        nodes.extend(connection['nodes'])
        info = connection['pageInfo']
        if not info.get('hasNextPage') or (limit and len(nodes) >= limit):
            return nodes
        next_cursor = info.get('endCursor')
        if not next_cursor or next_cursor in seen or not connection['nodes']:
            raise RuntimeError('Shopify pagination did not advance')
        seen.add(next_cursor)
        cursor = next_cursor


def get_products(limit=None):
    return _paginate('products', PRODUCT_FIELDS, max(1,int(limit)) if limit is not None else None)


def get_orders(limit=None):
    return _paginate('orders', ORDER_FIELDS, max(1,int(limit)) if limit is not None else None)


def get_store_context():
    scope_data = _graphql_request('query { currentAppInstallation { accessScopes { handle } } }')
    scopes = {s['handle'] for s in scope_data['currentAppInstallation']['accessScopes']}
    products = get_products()
    orders = get_orders()
    return {'products':products,'orders':orders,'product_count':len(products),'order_count':len(orders),
            'coverage':{'products':'all accessible products; all pages fetched',
                        'orders':'all accessible orders' if 'read_all_orders' in scopes else 'accessible orders from the last 60 days only',
                        'all_order_history_permission':'read_all_orders' in scopes,
                        'fetched_at':datetime.now(timezone.utc).isoformat()}}
