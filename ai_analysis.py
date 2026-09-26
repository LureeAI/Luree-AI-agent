from flask import Blueprint, jsonify

ai_analysis = Blueprint("ai_analysis", name)


def analyze_products(products):
    if not isinstance(products, list):
        return {
            "success": False,
            "error": "Products data must be a list."
        }

    if len(products) == 0:
        return {
            "success": True,
            "product_count": 0,
            "summary": "No products were found.",
            "out_of_stock": [],
            "low_stock": [],
            "high_stock": []
        }

    out_of_stock = []
    low_stock = []
    high_stock = []

    total_inventory = 0

    for product in products:
        title = product.get("title", "Unknown product")
        inventory = product.get("totalInventory", 0)

        if inventory is None:
            inventory = 0

        try:
            inventory = int(inventory)
        except (TypeError, ValueError):
            inventory = 0

        total_inventory += inventory

        product_info = {
            "title": title,
            "inventory": inventory
        }

        if inventory <= 0:
            out_of_stock.append(product_info)
        elif inventory <= 10:
            low_stock.append(product_info)
        elif inventory >= 100:
            high_stock.append(product_info)

    product_count = len(products)

    average_inventory = (
        round(total_inventory / product_count, 2)
        if product_count > 0
        else 0
    )

    return {
        "success": True,
        "product_count": product_count,
        "total_inventory": total_inventory,
        "average_inventory": average_inventory,
        "out_of_stock_count": len(out_of_stock),
        "low_stock_count": len(low_stock),
        "high_stock_count": len(high_stock),
        "out_of_stock": out_of_stock,
        "low_stock": low_stock,
        "high_stock": high_stock
    }


@ai_analysis.route("/analysis/health", methods=["GET"])
def analysis_health():
    return jsonify({
        "
