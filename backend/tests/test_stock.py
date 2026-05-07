from httpx import AsyncClient

# Reusable helper — creates a product and returns the full response dict
async def create_product(client: AsyncClient, admin_token: str, quantity: int = 0) -> dict:
    response = await client.post(
        "/products",
        json={
            "name": "Test Product",
            "sku": f"SKU-{quantity}-{id(client)}",
            "price": "10.00",
            "quantity": quantity,
            "low_stock_threshold": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    return response.json()


# -----------------------------------------------------------------------------
# ADJUST STOCK — Happy Path
# -----------------------------------------------------------------------------

async def test_receive_stock(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "RECEIVE",
            "quantity_change": 50,
            "note": "Initial delivery",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["movement_type"] == "RECEIVE"
    assert data["quantity_change"] == 50
    assert data["quantity_before"] == 0
    assert data["quantity_after"] == 50
    assert data["note"] == "Initial delivery"
    assert data["product_id"] == product["id"]


async def test_ship_stock(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "SHIP",
            "quantity_change": -30,
            "note": "Order #1001",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["movement_type"] == "SHIP"
    assert data["quantity_change"] == -30
    assert data["quantity_before"] == 100
    assert data["quantity_after"] == 70


async def test_adjust_stock_upward(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=20)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "ADJUST",
            "quantity_change": 5,
            "note": "Recount found extra units",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["quantity_before"] == 20
    assert data["quantity_after"] == 25


async def test_adjust_stock_downward(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=20)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "ADJUST",
            "quantity_change": -3,
            "note": "3 units damaged",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["quantity_before"] == 20
    assert data["quantity_after"] == 17


# -----------------------------------------------------------------------------
# ADJUST STOCK — Validation & Business Rules
# -----------------------------------------------------------------------------

async def test_ship_more_than_available_returns_409(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=5)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "SHIP",
            "quantity_change": -10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 409


async def test_receive_with_negative_quantity_returns_422(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "RECEIVE",
            "quantity_change": -10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422


async def test_ship_with_positive_quantity_returns_422(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=100)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "SHIP",
            "quantity_change": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422


async def test_quantity_change_zero_returns_422(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=10)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "ADJUST",
            "quantity_change": 0,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422


async def test_adjust_stock_product_not_found_returns_404(client: AsyncClient, admin_token: str):
    response = await client.post(
        "/stock/non-existent-id/adjust",
        json={
            "movement_type": "RECEIVE",
            "quantity_change": 10,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404


# -----------------------------------------------------------------------------
# ADJUST STOCK — Auth & Permissions
# -----------------------------------------------------------------------------

async def test_adjust_stock_requires_admin(client: AsyncClient, admin_token: str, user_token: str):
    product = await create_product(client, admin_token, quantity=10)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "RECEIVE",
            "quantity_change": 10,
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 403


async def test_adjust_stock_requires_auth(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=10)

    response = await client.post(
        f"/stock/{product['id']}/adjust",
        json={
            "movement_type": "RECEIVE",
            "quantity_change": 10,
        },
    )

    assert response.status_code == 401


# -----------------------------------------------------------------------------
# MOVEMENT HISTORY
# -----------------------------------------------------------------------------

async def test_movement_history_returns_movements(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        f"/stock/{product['id']}/adjust",
        json={"movement_type": "RECEIVE", "quantity_change": 100},
        headers=headers,
    )
    await client.post(
        f"/stock/{product['id']}/adjust",
        json={"movement_type": "SHIP", "quantity_change": -20},
        headers=headers,
    )

    response = await client.get(
        f"/stock/{product['id']}/history",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    # Newest first — SHIP was last
    assert data["items"][0]["movement_type"] == "SHIP"
    assert data["items"][1]["movement_type"] == "RECEIVE"


async def test_movement_history_empty_product(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)

    response = await client.get(
        f"/stock/{product['id']}/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["total_pages"] == 1


async def test_movement_history_pagination(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)
    headers = {"Authorization": f"Bearer {admin_token}"}

    for i in range(1, 6):
        await client.post(
            f"/stock/{product['id']}/adjust",
            json={"movement_type": "RECEIVE", "quantity_change": i},
            headers=headers,
        )

    response = await client.get(
        f"/stock/{product['id']}/history?page=1&page_size=2",
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert data["total_pages"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2


async def test_movement_history_regular_user_can_view(
    client: AsyncClient, admin_token: str, user_token: str
):
    product = await create_product(client, admin_token, quantity=0)

    response = await client.get(
        f"/stock/{product['id']}/history",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200


async def test_movement_history_requires_auth(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)

    response = await client.get(f"/stock/{product['id']}/history")

    assert response.status_code == 401


async def test_movement_history_product_not_found(client: AsyncClient, admin_token: str):
    response = await client.get(
        "/stock/non-existent-id/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404