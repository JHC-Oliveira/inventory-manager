from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from app.config import get_settings

API_PREFIX = get_settings().api_prefix

# Reusable helper — creates a product and returns the full response dict
async def create_product(client: AsyncClient, admin_token: str, quantity: int = 0) -> dict:
    response = await client.post(
        f"{API_PREFIX}/products",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
        json={
            "movement_type": "ADJUST",
            "quantity_change": 0,
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 422


async def test_adjust_stock_product_not_found_returns_404(client: AsyncClient, admin_token: str):
    response = await client.post(
        f"{API_PREFIX}/stock/non-existent-id/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
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
        f"{API_PREFIX}/stock/{product['id']}/adjust",
        json={"movement_type": "RECEIVE", "quantity_change": 100},
        headers=headers,
    )
    await client.post(
        f"{API_PREFIX}/stock/{product['id']}/adjust",
        json={"movement_type": "SHIP", "quantity_change": -20},
        headers=headers,
    )

    response = await client.get(
        f"{API_PREFIX}/stock/{product['id']}/history",
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
        f"{API_PREFIX}/stock/{product['id']}/history",
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
            f"{API_PREFIX}/stock/{product['id']}/adjust",
            json={"movement_type": "RECEIVE", "quantity_change": i},
            headers=headers,
        )

    response = await client.get(
        f"{API_PREFIX}/stock/{product['id']}/history?page=1&page_size=2",
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
        f"{API_PREFIX}/stock/{product['id']}/history",
        headers={"Authorization": f"Bearer {user_token}"},
    )

    assert response.status_code == 200


async def test_movement_history_requires_auth(client: AsyncClient, admin_token: str):
    product = await create_product(client, admin_token, quantity=0)

    response = await client.get(f"{API_PREFIX}/stock/{product['id']}/history")

    assert response.status_code == 401


async def test_movement_history_product_not_found(client: AsyncClient, admin_token: str):
    response = await client.get(
        f"{API_PREFIX}/stock/non-existent-id/history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 404
    
#-------------------------------------------------------------    
#                    Movement history cache tests
#-------------------------------------------------------------

# --------------------- History cache hit --------------------

async def test_movement_history_cache_hit_returns_cached_response(
    client: AsyncClient,
    admin_token: str,
):
    product = await create_product(client, admin_token, quantity=0)

    cached_payload = {
        "items": [
            {
                "id": "stk_test_1",
                "product_id": product["id"],
                "product_sku": product["sku"],
                "movement_type": "SHIP",
                "quantity_change": -5,
                "quantity_before": 20,
                "quantity_after": 15,
                "note": "From Redis cache",
                "created_by": "usr_test_123",
                "created_at": "2026-05-27T00:00:00",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
        "total_pages": 1,
    }

    with patch("app.services.stock_service.cache_get", new=AsyncMock(return_value=cached_payload)) as mock_cache_get, \
         patch("app.services.stock_service.cache_set", new=AsyncMock()) as mock_cache_set:

        response = await client.get(
            f"{API_PREFIX}/stock/{product['id']}/history",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["movement_type"] == "SHIP"
    assert data["items"][0]["note"] == "From Redis cache"

    mock_cache_get.assert_awaited_once()
    mock_cache_set.assert_not_awaited()
    
    
# --------------------- History cache miss -----------------------

async def test_movement_history_cache_miss_sets_cache(
    client: AsyncClient,
    admin_token: str,
):
    product = await create_product(client, admin_token, quantity=0)
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(
        f"{API_PREFIX}/stock/{product['id']}/adjust",
        json={"movement_type": "RECEIVE", "quantity_change": 25},
        headers=headers,
    )

    with patch("app.services.stock_service.cache_get", new=AsyncMock(return_value=None)) as mock_cache_get, \
         patch("app.services.stock_service.cache_set", new=AsyncMock()) as mock_cache_set:

        response = await client.get(
            f"{API_PREFIX}/stock/{product['id']}/history",
            headers=headers,
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1

    mock_cache_get.assert_awaited_once()
    mock_cache_set.assert_awaited_once()

    await_args = mock_cache_set.await_args
    assert await_args is not None
    
    args = await_args.args
    assert args[0].startswith(f"stock:history:{product['id']}:")
    assert args[2] == 60
    
    
# ----------------- Adjust stock invalidates history cache ---------------

async def test_adjust_stock_invalidates_history_cache(
    client: AsyncClient,
    admin_token: str,
):
    product = await create_product(client, admin_token, quantity=10)

    with patch("app.services.stock_service.cache_delete_pattern", new=AsyncMock()) as mock_cache_delete_pattern:
        response = await client.post(
            f"{API_PREFIX}/stock/{product['id']}/adjust",
            json={
                "movement_type": "RECEIVE",
                "quantity_change": 5,
                "note": "Restock",
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert response.status_code == 200
    
    assert mock_cache_delete_pattern.await_count == 3
    mock_cache_delete_pattern.assert_any_await(f"stock:history:{product['id']}:*")
    mock_cache_delete_pattern.assert_any_await("products:list:*")
    mock_cache_delete_pattern.assert_any_await("stock:movements:*")


    
    
# ----------- Movement history regular user -----------------

async def test_movement_history_cache_hit_regular_user_can_view(
    client: AsyncClient,
    admin_token: str,
    user_token: str,
):
    product = await create_product(client, admin_token, quantity=0)

    cached_payload = {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 10,
        "total_pages": 1,
    }

    with patch("app.services.stock_service.cache_get", new=AsyncMock(return_value=cached_payload)) as mock_cache_get:
        response = await client.get(
            f"{API_PREFIX}/stock/{product['id']}/history",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    assert response.json()["total"] == 0
    mock_cache_get.assert_awaited_once()