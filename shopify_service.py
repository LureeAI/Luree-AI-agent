import requests

import shopify_auth as shopify_module


API_VERSION = "2026-04"


def _get_connection():
    shop = shopify_module.connected_shop
    access_token = shopify_module.shopify_access_token

    if not shop or not access_token:
        raise RuntimeError("Shopify is not connected")

    return shop, access_token


def _graphql_request(query):
    shop, access_token = _get_connection()

    url = (
        f"https://{shop}/admin/api/"
        f"{API_VERSION}/graphql.json"
    )

    response = requests.post(
        url,
        headers={
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        },
        json={
            "query": query
        },
        timeout=30,
    )

    response.raise_for_status()

    result = response.json()

    if result.get("errors"):
        raise RuntimeError(
            f"Shopify GraphQL error: {result['errors']}"
        )

    return result.get("data", {})


def get_products(limit=20):
    limit = max(1, min(int(limit), 50))

    query = f"""
    query {{
      products(first: {limit}) {{
        nodes {{
          id
          title
          handle
          status
          vendor
          productType
          totalInventory
          createdAt
          updatedAt
          priceRangeV2 {{
            minVariantPrice {{
              amount
              currencyCode
            }}
            maxVariantPrice {{
              amount
              currencyCode
            }}
          }}
        }}
      }}
    }}
    """

    data = _graphql_request(query)

    return data.get("products", {}).get("nodes", [])


def get_orders(limit=20):
    limit = max(1, min(int(limit), 50))

    query = f"""
    query {{
      orders(first: {limit}, reverse: true) {{
        nodes {{
          id
          name
          createdAt
          displayFinancialStatus
          displayFulfillmentStatus
          totalPriceSet {{
            shopMoney {{
              amount
              currencyCode
            }}
          }}
        }}
      }}
    }}
    """

    data = _graphql_request(query)

    return data.get("orders", {}).get("nodes", [])


def get_store_context():
    products = get_products()
    orders = get_orders()

    return {
        "products": products,
        "orders": orders,
        "product_count": len(products),
        "order_count": len(orders),
    }
