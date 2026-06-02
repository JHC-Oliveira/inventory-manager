import pytest

API_PREFIX = "/api/v1"

@pytest.mark.asyncio
async def test_register_success(client):
    response = await client.post(f"{API_PREFIX}/auth/register", json={
        "email": "joao@example.com",
        "password": "StrongPass123",
        "full_name": "Joao Henrique"
    })
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    payload = {
        "email": "joao@example.com",
        "password": "StrongPass123",
        "full_name": "Joao Henrique"
    }
    await client.post(f"{API_PREFIX}/auth/register", json=payload)
    response = await client.post(f"{API_PREFIX}/auth/register", json=payload)
    assert response.status_code == 409  # your router raises 409 CONFLICT


@pytest.mark.asyncio
async def test_login_success(client):
    await client.post(f"{API_PREFIX}/auth/register", json={
        "email": "joao@example.com",
        "password": "StrongPass123",
        "full_name": "Joao Henrique"
    })
    response = await client.post(f"{API_PREFIX}/auth/login", data={
        "username": "joao@example.com",
        "password": "StrongPass123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(f"{API_PREFIX}/auth/register", json={
        "email": "joao@example.com",
        "password": "StrongPass123",
        "full_name": "Joao Henrique"
    })
    response = await client.post(f"{API_PREFIX}/auth/login", data={
        "username": "joao@example.com",
        "password": "WrongPassword1"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client):
    response = await client.post(f"{API_PREFIX}/auth/login", data={
        "username": "nobody@example.com",
        "password": "StrongPass123"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_valid_token(client):
    await client.post(f"{API_PREFIX}/auth/register", json={
        "email": "joao@example.com",
        "password": "StrongPass123",
        "full_name": "Joao Henrique"
    })
    login = await client.post(f"{API_PREFIX}/auth/login", data={
        "username": "joao@example.com",
        "password": "StrongPass123"
    })
    token = login.json()["access_token"]
    response = await client.get(f"{API_PREFIX}/me", headers={
        "Authorization": f"Bearer {token}"
    })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_protected_route_without_token(client):
    response = await client.get(f"{API_PREFIX}/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_with_invalid_token(client):
    response = await client.get(f"{API_PREFIX}/me", headers={
        "Authorization": "Bearer invalidtoken123"
    })
    assert response.status_code == 401