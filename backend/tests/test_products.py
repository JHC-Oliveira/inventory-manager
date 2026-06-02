from httpx import AsyncClient
from unittest.mock import AsyncMock, patch

API_PREFIX = "/api/v1"

# Reusable product payload
PRODUCT_PAYLOAD = {
    "name": "Test T-Shirt",
    "description": "A comfortable cotton t-shirt",
    "sku": "TSHIRT-BLU-L",
    "price": "29.99",
    "quantity": 100,
    "low_stock_threshold": 10,
}


# -----------------------------------------------------------------------------
# CREATE
# -----------------------------------------------------------------------------
async def test_admin_can_create_product(client: AsyncClient, admin_token: str):
    response = await client.post(
        f"{API_PREFIX}/products",
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "TSHIRT-BLU-L"
    assert data["name"] == "Test T-Shirt"
    assert float(data["price"]) == 29.99
    assert data["is_active"] is True
    assert data["is_low_stock"] is False
    assert "id" in data


async def test_regular_user_cannot_create_product(client: AsyncClient, user_token: str):
    response = await client.post(
        f"{API_PREFIX}/products",
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_unauthenticated_cannot_create_product(client: AsyncClient):
    response = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD)
    assert response.status_code == 401


async def test_duplicate_sku_rejected(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    response = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    assert response.status_code == 409
    assert "already exists" in response.json()["message"].lower()


async def test_sku_is_stored_uppercase(client: AsyncClient, admin_token: str):
    payload = {**PRODUCT_PAYLOAD, "sku": "tshirt-blu-l"}  # lowercase
    response = await client.post(
        f"{API_PREFIX}/products",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 201
    assert response.json()["sku"] == "TSHIRT-BLU-L"  # stored uppercase


# -----------------------------------------------------------------------------
# LIST
# -----------------------------------------------------------------------------
async def test_logged_in_user_can_list_products(client: AsyncClient, user_token: str, admin_token: str):
    # Admin creates a product first
    await client.post(
        f"{API_PREFIX}/products",
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Regular user lists products
    response = await client.get(
        f"{API_PREFIX}/products",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert len(data["items"]) == 1


async def test_unauthenticated_cannot_list_products(client: AsyncClient):
    response = await client.get(f"{API_PREFIX}/products")
    assert response.status_code == 401


async def test_pagination_works(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Create 3 products with different SKUs
    for i in range(3):
        await client.post(
            f"{API_PREFIX}/products",
            json={**PRODUCT_PAYLOAD, "sku": f"PRODUCT-{i}"},
            headers=headers,
        )
    # Request page 1 with page_size=2
    response = await client.get(
        f"{API_PREFIX}/products?page=1&page_size=2",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert data["total_pages"] == 2
    assert len(data["items"]) == 2


# -----------------------------------------------------------------------------
# GET ONE
# -----------------------------------------------------------------------------
async def test_get_product_by_id(client: AsyncClient, user_token: str, admin_token: str):
    create = await client.post(
        f"{API_PREFIX}/products",
        json=PRODUCT_PAYLOAD,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    product_id = create.json()["id"]

    response = await client.get(
        f"{API_PREFIX}/products/{product_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 200
    assert response.json()["id"] == product_id


async def test_get_nonexistent_product_returns_404(client: AsyncClient, user_token: str):
    response = await client.get(
        f"{API_PREFIX}/products/nonexistent-id-999",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 404


# -----------------------------------------------------------------------------
# UPDATE
# -----------------------------------------------------------------------------
async def test_admin_can_update_product(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    response = await client.put(
        f"{API_PREFIX}/products/{product_id}",
        json={"price": "39.99", "quantity": 50},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert float(data["price"]) == 39.99
    assert data["quantity"] == 50
    assert data["name"] == "Test T-Shirt"  # unchanged


async def test_empty_update_rejected(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    response = await client.put(
        f"{API_PREFIX}/products/{product_id}",
        json={},  # nothing sent
        headers=headers,
    )
    assert response.status_code == 422


async def test_regular_user_cannot_update_product(
    client: AsyncClient, user_token: str, admin_token: str
):
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers_admin)
    product_id = create.json()["id"]

    response = await client.put(
        f"{API_PREFIX}/products/{product_id}",
        json={"price": "9.99"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


# -----------------------------------------------------------------------------
# DELETE
# -----------------------------------------------------------------------------
async def test_admin_can_delete_product(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    response = await client.delete(f"{API_PREFIX}/products/{product_id}", headers=headers)
    assert response.status_code == 204


async def test_deleted_product_not_in_list(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    # Delete it
    await client.delete(f"{API_PREFIX}/products/{product_id}", headers=headers)

    # Should not appear in list
    response = await client.get(f"{API_PREFIX}/products", headers=headers)
    assert response.json()["total"] == 0


async def test_deleted_product_returns_404(client: AsyncClient, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    await client.delete(f"{API_PREFIX}/products/{product_id}", headers=headers)

    # Direct fetch should 404
    response = await client.get(f"{API_PREFIX}/products/{product_id}", headers=headers)
    assert response.status_code == 404


async def test_regular_user_cannot_delete_product(
    client: AsyncClient, user_token: str, admin_token: str
):
    headers_admin = {"Authorization": f"Bearer {admin_token}"}
    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers_admin)
    product_id = create.json()["id"]

    response = await client.delete(
        f"{API_PREFIX}/products/{product_id}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403
    
#-------------------------------------------------------------    
#                    Redis cache tests
#-------------------------------------------------------------

# -------------------- Cache hit -----------------------------

async def test_get_products_cache_hit_returns_cached_response(
    client: AsyncClient,
    user_token: str,
):
    cached_payload = {
        "items": [
            {
                "id": "prd_test_123",
                "name": "Cached T-Shirt",
                "description": "From Redis cache",
                "sku": "CACHED-SKU-1",
                "price": "19.99",
                "quantity": 42,
                "low_stock_threshold": 5,
                "is_active": True,
                "is_low_stock": False,
                "created_by": "usr_test_123",
                "created_at": "2026-05-26T12:00:00",
                "updated_at": "2026-05-26T12:00:00",
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10,
        "total_pages": 1,
    }

    with patch("app.services.product_service.cache_get", new=AsyncMock(return_value=cached_payload)) as mock_cache_get, \
         patch("app.services.product_service.cache_set", new=AsyncMock()) as mock_cache_set:

        response = await client.get(
            f"{API_PREFIX}/products",
            headers={"Authorization": f"Bearer {user_token}"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku"] == "CACHED-SKU-1"

    mock_cache_get.assert_awaited_once()
    mock_cache_set.assert_not_awaited()
    
    
# ----------------------- Cache miss tests -----------------------

async def test_get_products_cache_miss_sets_cache(
    client: AsyncClient,
    admin_token: str,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)

    with patch("app.services.product_service.cache_get", new=AsyncMock(return_value=None)) as mock_cache_get, \
         patch("app.services.product_service.cache_set", new=AsyncMock()) as mock_cache_set:

        response = await client.get(f"{API_PREFIX}/products", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1

    mock_cache_get.assert_awaited_once()
    mock_cache_set.assert_awaited_once()
    
    
# ----------------------- Create invalidation test --------------------------

async def test_create_product_invalidates_products_cache(
    client: AsyncClient,
    admin_token: str,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    with patch("app.services.product_service.cache_delete_pattern", new=AsyncMock()) as mock_cache_delete_pattern:
        response = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)

    assert response.status_code == 201
    mock_cache_delete_pattern.assert_awaited_once_with("products:list:*")
    
    
# ---------------------- Update invalidation test ---------------------------
async def test_update_product_invalidates_products_cache(
    client: AsyncClient,
    admin_token: str,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    with patch("app.services.product_service.cache_delete_pattern", new=AsyncMock()) as mock_cache_delete_pattern:
        response = await client.put(
            f"{API_PREFIX}/products/{product_id}",
            json={"price": "39.99"},
            headers=headers,
        )

    assert response.status_code == 200
    mock_cache_delete_pattern.assert_awaited_once_with("products:list:*")
    
    
# --------------------------- Delete invalidation test -------------------------

async def test_delete_product_invalidates_products_cache(
    client: AsyncClient,
    admin_token: str,
):
    headers = {"Authorization": f"Bearer {admin_token}"}

    create = await client.post(f"{API_PREFIX}/products", json=PRODUCT_PAYLOAD, headers=headers)
    product_id = create.json()["id"]

    with patch("app.services.product_service.cache_delete_pattern", new=AsyncMock()) as mock_cache_delete_pattern:
        response = await client.delete(f"{API_PREFIX}/products/{product_id}", headers=headers)

    assert response.status_code == 204
    mock_cache_delete_pattern.assert_awaited_once_with("products:list:*")