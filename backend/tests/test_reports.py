from httpx import AsyncClient
from app.config import get_settings

API_PREFIX = get_settings().api_prefix

# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------

async def create_product(
    client: AsyncClient,
    admin_token: str,
    sku: str,
    quantity: int,
    low_stock_threshold: int = 10,
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/products",
        json={
            "name": f"Product {sku}",
            "sku": sku,
            "price": "10.00",
            "quantity": quantity,
            "low_stock_threshold": low_stock_threshold,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()


async def create_order_with_item(
    client: AsyncClient,
    user_token: str,
    product_id: str,
    quantity: int,
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test Customer",
            "items": [
                {
                    "product_id": product_id,
                    "quantity": quantity,
                }
            ],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 201
    return response.json()


async def adjust_stock(
    client: AsyncClient,
    admin_token: str,
    product_id: str,
    movement_type: str,
    quantity_change: int,
    note: str | None = None,
) -> dict:
    payload = {
        "movement_type": movement_type,
        "quantity_change": quantity_change,
    }
    if note is not None:
        payload["note"] = note

    response = await client.post(
        f"{API_PREFIX}/stock/{product_id}/adjust",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    return response.json()
# -----------------------------------------------------------------------------
# STOCK SUMMARY
# -----------------------------------------------------------------------------

async def test_stock_summary_admin_can_view(client: AsyncClient, admin_token: str):
    p1 = await create_product(client, admin_token, "SUM-001", quantity=5)
    p2 = await create_product(client, admin_token, "SUM-002", quantity=3)

    response = await client.get(
        f"{API_PREFIX}/reports/stock-summary",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_products"] == 2
    assert len(data["items"]) == 2
    assert data["total_inventory_value"] == "80.00"
    assert data["items"][0]["sku"] in {p1["sku"], p2["sku"]}
    assert data["items"][1]["sku"] in {p1["sku"], p2["sku"]}


async def test_stock_summary_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(
        f"{API_PREFIX}/reports/stock-summary",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_stock_summary_requires_auth(client: AsyncClient):
    response = await client.get(f"{API_PREFIX}/reports/stock-summary")
    assert response.status_code == 401


# -----------------------------------------------------------------------------
# LOW STOCK
# -----------------------------------------------------------------------------

async def test_low_stock_admin_can_view(client: AsyncClient, admin_token: str):
    low = await create_product(client, admin_token, "LOW-001", quantity=2, low_stock_threshold=5)
    await create_product(client, admin_token, "OK-001", quantity=20, low_stock_threshold=5)

    response = await client.get(
        f"{API_PREFIX}/reports/low-stock",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == low["id"]
    assert data["items"][0]["sku"] == low["sku"]


async def test_low_stock_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(
        f"{API_PREFIX}/reports/low-stock",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


# -----------------------------------------------------------------------------
# TOP PRODUCTS
# -----------------------------------------------------------------------------

async def test_top_products_admin_can_view(client: AsyncClient, admin_token: str, user_token: str):
    product = await create_product(client, admin_token, "TOP-001", quantity=50)

    await create_order_with_item(client, user_token, product["id"], quantity=2)
    await create_order_with_item(client, user_token, product["id"], quantity=3)

    response = await client.get(
        f"{API_PREFIX}/reports/top-products",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["product_sku"] == product["sku"]
    assert data["items"][0]["total_quantity"] == 5
    assert data["items"][0]["total_orders"] == 2
    assert data["items"][0]["total_revenue"] == "50.00"


async def test_top_products_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(
        f"{API_PREFIX}/reports/top-products",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


# -----------------------------------------------------------------------------
# MOVEMENT HISTORY
# -----------------------------------------------------------------------------

async def test_movement_history_admin_can_view(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, "HIS-001", quantity=10)

    await adjust_stock(client, admin_token, product["id"], "RECEIVE", 5, "Restock")
    await adjust_stock(client, admin_token, product["id"], "SHIP", -2, "Sale")

    response = await client.get(
        f"{API_PREFIX}/reports/movement-history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 10
    assert data["total_pages"] == 1
    assert data["items"][0]["movement_type"] == "SHIP"
    assert data["items"][1]["movement_type"] == "RECEIVE"
    assert data["items"][0]["created_by"] is not None


async def test_movement_history_pagination(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, "HIS-002", quantity=0)

    for i in range(5):
        await adjust_stock(client, admin_token, product["id"], "RECEIVE", i + 1, f"Move {i + 1}")

    response = await client.get(
        f"{API_PREFIX}/reports/movement-history?page=1&page_size=2",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2


async def test_movement_history_requires_admin(client: AsyncClient, user_token: str):
    response = await client.get(
        f"{API_PREFIX}/reports/movement-history",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_movement_history_requires_auth(client: AsyncClient):
    response = await client.get(f"{API_PREFIX}/reports/movement-history")
    assert response.status_code == 401