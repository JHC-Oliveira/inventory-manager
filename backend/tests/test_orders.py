import pytest
from httpx import AsyncClient
from app.config import get_settings

API_PREFIX = get_settings().api_prefix


# ---------------------------------------------------------------------------
# Helper — creates a product and returns its full response dict
# Same pattern as test_stock.py's create_product helper
# ---------------------------------------------------------------------------

async def create_product(
    client: AsyncClient,
    admin_token: str,
    sku: str = "TSHIRT-BLU-L",
    quantity: int = 100,
    price: float = 29.99,
) -> dict:
    response = await client.post(
        f"{API_PREFIX}/products",
        json={
            "name": "Test T-Shirt",
            "sku": sku,
            "price": price,
            "quantity": quantity,
            "low_stock_threshold": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# CREATE ORDER — Happy Path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_user_can_create_order(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "João Henrique",
            "items": [{"product_id": product["id"], "quantity": 2}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["customer_name"] == "João Henrique"
    assert data["status"] == "PENDING"
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 2
    assert float(data["items"][0]["unit_price"]) == 29.99
    assert float(data["items"][0]["subtotal"]) == 59.98
    assert data["items"][0]["product_sku"] == "TSHIRT-BLU-L"
    assert data["items"][0]["product_name"] == "Test T-Shirt"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_order_reduces_stock(client: AsyncClient, user_token: str, admin_token: str):
    """Stock must decrease by exactly the ordered quantity."""
    product = await create_product(client, admin_token, quantity=100)

    await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test Customer",
            "items": [{"product_id": product["id"], "quantity": 30}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    # Check product stock was reduced
    response = await client.get(
        f"{API_PREFIX}/products/{product['id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["quantity"] == 70  # 100 - 30


@pytest.mark.asyncio
async def test_create_order_multiple_items(client: AsyncClient, user_token: str, admin_token: str):
    """One order with two different products — both stock levels update."""
    product_a = await create_product(client, admin_token, sku="PROD-A", quantity=50)
    product_b = await create_product(client, admin_token, sku="PROD-B", quantity=80)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Multi Item Customer",
            "items": [
                {"product_id": product_a["id"], "quantity": 10},
                {"product_id": product_b["id"], "quantity": 20},
            ],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 201
    assert len(response.json()["items"]) == 2

    # Verify both stock levels
    stock_a = await client.get(f"{API_PREFIX}/products/{product_a['id']}", headers={"Authorization": f"Bearer {user_token}"})
    stock_b = await client.get(f"{API_PREFIX}/products/{product_b['id']}", headers={"Authorization": f"Bearer {user_token}"})
    assert stock_a.json()["quantity"] == 40   # 50 - 10
    assert stock_b.json()["quantity"] == 60   # 80 - 20


@pytest.mark.asyncio
async def test_create_order_generates_ship_movements(client: AsyncClient, user_token: str, admin_token: str):
    """Every item in the order must generate a SHIP stock movement."""
    product = await create_product(client, admin_token, quantity=100)

    await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Audit Test",
            "items": [{"product_id": product["id"], "quantity": 5}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    history = await client.get(
        f"{API_PREFIX}/stock/{product['id']}/history",
        headers={"Authorization": f"Bearer {user_token}"},
    )    

    assert history.status_code == 200
    data = history.json()
    assert data["total"] == 1
    assert data["items"][0]["movement_type"] == "SHIP"
    assert data["items"][0]["quantity_change"] == -5
    assert data["items"][0]["quantity_before"] == 100
    assert data["items"][0]["quantity_after"] == 95


# ---------------------------------------------------------------------------
# CREATE ORDER — Validation & Business Rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_order_insufficient_stock_returns_409(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Cannot order more units than available stock."""
    product = await create_product(client, admin_token, quantity=5)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Greedy Customer",
            "items": [{"product_id": product["id"], "quantity": 10}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 409
    assert "insufficient stock" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_create_order_product_not_found_returns_404(
    client: AsyncClient, user_token: str
):
    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test",
            "items": [{"product_id": "non-existent-id", "quantity": 1}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_order_empty_items_returns_422(
    client: AsyncClient, user_token: str
):
    """An order with zero items must be rejected by the schema."""
    response = await client.post(
        f"{API_PREFIX}/orders",
        json={"customer_name": "Test", "items": []},
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_order_zero_quantity_returns_422(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Quantity must be greater than zero."""
    product = await create_product(client, admin_token, quantity=100)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test",
            "items": [{"product_id": product["id"], "quantity": 0}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_order_duplicate_product_returns_422(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Same product_id appearing twice in items must be rejected."""
    product = await create_product(client, admin_token, quantity=100)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test",
            "items": [
                {"product_id": product["id"], "quantity": 1},
                {"product_id": product["id"], "quantity": 2},  # duplicate
            ],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_order_inactive_product_returns_404(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Soft-deleted products cannot be ordered."""
    product = await create_product(client, admin_token, quantity=100)

    # Soft-delete the product
    await client.delete(
        f"{API_PREFIX}/products/{product['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_order_partial_failure_rolls_back(
    client: AsyncClient, user_token: str, admin_token: str
):
    """
    If item 2 of 2 fails (insufficient stock), the entire order
    must be rolled back — no partial order, no stock change on item 1.
    """
    product_a = await create_product(client, admin_token, sku="ROLLBACK-A", quantity=50)
    product_b = await create_product(client, admin_token, sku="ROLLBACK-B", quantity=2)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Rollback Test",
            "items": [
                {"product_id": product_a["id"], "quantity": 10},   # fine
                {"product_id": product_b["id"], "quantity": 99},   # fails
            ],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 409

    # Product A stock must be untouched — the whole order rolled back
    stock_a = await client.get(
        f"{API_PREFIX}/products/{product_a['id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert stock_a.json()["quantity"] == 50  # unchanged ✅


# ---------------------------------------------------------------------------
# CREATE ORDER — Auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_order_requires_auth(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    response = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Test",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        # No Authorization header
    )

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# CANCEL ORDER — Happy Path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_admin_can_cancel_order(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "To Cancel",
            "items": [{"product_id": product["id"], "quantity": 10}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert order.status_code == 201
    order_id = order.json()["id"]

    response = await client.patch(
        f"{API_PREFIX}/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_cancel_order_restores_stock(client: AsyncClient, user_token: str, admin_token: str):
    """Stock must be fully restored after cancellation."""
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Restore Test",
            "items": [{"product_id": product["id"], "quantity": 25}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    # Stock is now 75
    await client.patch(
        f"{API_PREFIX}/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Stock must be back to 100
    stock = await client.get(
        f"{API_PREFIX}/products/{product['id']}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert stock.json()["quantity"] == 100  # fully restored ✅


@pytest.mark.asyncio
async def test_cancel_order_generates_receive_movements(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Cancellation must create a RECEIVE movement for each item."""
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Movement Test",
            "items": [{"product_id": product["id"], "quantity": 10}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    await client.patch(
        f"{API_PREFIX}/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    history = await client.get(
        f"{API_PREFIX}/stock/{product['id']}/history",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    data = history.json()

    # Newest first: RECEIVE (cancel) then SHIP (order)
    assert data["total"] == 2
    assert data["items"][0]["movement_type"] == "RECEIVE"
    assert data["items"][0]["quantity_change"] == 10
    assert data["items"][1]["movement_type"] == "SHIP"


# ---------------------------------------------------------------------------
# CANCEL ORDER — Business Rules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cancel_already_cancelled_order_returns_409(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Cannot cancel an already-cancelled order."""
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Double Cancel",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    # First cancel — success
    await client.patch(
        f"{API_PREFIX}/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Second cancel — must fail
    response = await client.patch(
        f"{API_PREFIX}/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409
    assert "cannot be cancelled" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_cancel_non_existent_order_returns_404(
    client: AsyncClient, admin_token: str
):
    response = await client.patch(
        f"{API_PREFIX}/orders/non-existent-order-id/cancel",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# CANCEL ORDER — Auth
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_regular_user_cannot_cancel_order(
    client: AsyncClient, user_token: str, admin_token: str
):
    """Cancel is admin-only."""
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Auth Test",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    response = await client.patch(
        f"{API_PREFIX}/orders/{order_id}/cancel",
        headers={"Authorization": f"Bearer {user_token}"},  # user, not admin
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_cancel_order_requires_auth(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Auth Test",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    response = await client.patch(f"{API_PREFIX}/orders/{order_id}/cancel")  # no token

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET ONE ORDER
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_order_by_id(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Get Test",
            "items": [{"product_id": product["id"], "quantity": 3}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    response = await client.get(
        f"{API_PREFIX}/orders/{order_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == order_id
    assert data["customer_name"] == "Get Test"
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_get_non_existent_order_returns_404(client: AsyncClient, user_token: str):
    response = await client.get(
        f"{API_PREFIX}/orders/non-existent-id",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_order_requires_auth(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    order = await client.post(
        f"{API_PREFIX}/orders",
        json={
            "customer_name": "Auth Test",
            "items": [{"product_id": product["id"], "quantity": 1}],
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    order_id = order.json()["id"]

    response = await client.get(f"{API_PREFIX}/orders/{order_id}")  # no token

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# LIST ORDERS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_orders_returns_all(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)
    headers = {"Authorization": f"Bearer {user_token}"}

    # Create 3 orders
    for i in range(3):
        await client.post(
            f"{API_PREFIX}/orders",
            json={
                "customer_name": f"Customer {i}",
                "items": [{"product_id": product["id"], "quantity": 1}],
            },
            headers=headers,
        )

    response = await client.get(f"{API_PREFIX}/orders", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_list_orders_pagination(client: AsyncClient, user_token: str, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)
    headers = {"Authorization": f"Bearer {user_token}"}

    for i in range(5):
        await client.post(
            f"{API_PREFIX}/orders",
            json={
                "customer_name": f"Customer {i}",
                "items": [{"product_id": product["id"], "quantity": 1}],
            },
            headers=headers,
        )

    response = await client.get(f"{API_PREFIX}/orders?page=1&page_size=2", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


@pytest.mark.asyncio
async def test_list_orders_requires_auth(client: AsyncClient):
    response = await client.get(f"{API_PREFIX}/orders")  # no token

    assert response.status_code == 401