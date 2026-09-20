"""Todo tests."""

import pytest
from httpx import AsyncClient


async def register_and_get_token(client: AsyncClient, email: str) -> str:
    """Helper to register a user and return their access token."""
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password123"},
    )
    return response.json()["access_token"]


async def create_todo(
    client: AsyncClient,
    token: str,
    title: str = "Test Todo",
    description: str | None = None,
) -> dict:
    """Helper to create a todo and return the response JSON."""
    payload = {"title": title}
    if description is not None:
        payload["description"] = description
    response = await client.post(
        "/api/v1/todos",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Existing CRUD tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_todo(client: AsyncClient):
    """Test creating a new todo."""
    token = await register_and_get_token(client, "create@example.com")

    response = await client.post(
        "/api/v1/todos",
        json={"title": "Test Todo", "description": "A test todo item"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Todo"
    assert data["description"] == "A test todo item"
    assert data["completed"] is False


@pytest.mark.asyncio
async def test_get_todos(client: AsyncClient):
    """Test getting todo list."""
    token = await register_and_get_token(client, "list@example.com")
    await create_todo(client, token, title="List Todo")

    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 1


@pytest.mark.asyncio
async def test_update_todo(client: AsyncClient):
    """Test updating a todo."""
    token = await register_and_get_token(client, "update@example.com")
    todo = await create_todo(client, token, title="Update Me")

    response = await client.put(
        f"/api/v1/todos/{todo['id']}",
        json={"title": "Updated Title", "completed": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Title"


@pytest.mark.asyncio
async def test_delete_todo(client: AsyncClient):
    """Test deleting a todo."""
    token = await register_and_get_token(client, "delete@example.com")
    todo = await create_todo(client, token, title="Delete Me")

    response = await client.delete(
        f"/api/v1/todos/{todo['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_get_single_todo(client: AsyncClient):
    """Test getting a single todo by ID."""
    token = await register_and_get_token(client, "single@example.com")
    todo = await create_todo(client, token, title="Single Todo", description="Get me")

    response = await client.get(
        f"/api/v1/todos/{todo['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Single Todo"


# ---------------------------------------------------------------------------
# Tier 2 — 2A: Critical scenario tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_user_cannot_read_another_users_todo(client: AsyncClient):
    """B2: User A cannot GET a todo that belongs to User B."""
    token_a = await register_and_get_token(client, "owner_read_a@example.com")
    token_b = await register_and_get_token(client, "intruder_read_b@example.com")

    # User A creates a todo
    todo = await create_todo(client, token_a, title="User A Private Todo")

    # User B tries to read it
    response = await client.get(
        f"/api/v1/todos/{todo['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_update_another_users_todo(client: AsyncClient):
    """B2: User A cannot PUT a todo that belongs to User B."""
    token_a = await register_and_get_token(client, "owner_update_a@example.com")
    token_b = await register_and_get_token(client, "intruder_update_b@example.com")

    todo = await create_todo(client, token_a, title="User A Todo")

    response = await client.put(
        f"/api/v1/todos/{todo['id']}",
        json={"title": "Hacked"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_user_cannot_delete_another_users_todo(client: AsyncClient):
    """B2: User A cannot DELETE a todo that belongs to User B."""
    token_a = await register_and_get_token(client, "owner_delete_a@example.com")
    token_b = await register_and_get_token(client, "intruder_delete_b@example.com")

    todo = await create_todo(client, token_a, title="User A Todo")

    response = await client.delete(
        f"/api/v1/todos/{todo['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_toggle_completed_false_persists(client: AsyncClient):
    """B5: Setting completed=true then completed=false correctly persists as false."""
    token = await register_and_get_token(client, "toggle@example.com")
    todo = await create_todo(client, token, title="Toggle Me")
    todo_id = todo["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mark as completed
    r1 = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": True},
        headers=headers,
    )
    assert r1.status_code == 200
    assert r1.json()["completed"] is True

    # Unmark — this was broken before B5 fix
    r2 = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"completed": False},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["completed"] is False


@pytest.mark.asyncio
async def test_partial_update_preserves_description(client: AsyncClient):
    """Updating only title must not erase an existing description."""
    token = await register_and_get_token(client, "partial@example.com")
    todo = await create_todo(
        client, token, title="Original Title", description="Keep this description"
    )
    todo_id = todo["id"]
    headers = {"Authorization": f"Bearer {token}"}

    # Update title only — description should survive
    response = await client.put(
        f"/api/v1/todos/{todo_id}",
        json={"title": "New Title"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "New Title"
    assert data["description"] == "Keep this description"


@pytest.mark.asyncio
async def test_todo_list_is_user_scoped(client: AsyncClient):
    """User B's todo list must not contain todos created by User A."""
    token_a = await register_and_get_token(client, "scope_a@example.com")
    token_b = await register_and_get_token(client, "scope_b@example.com")

    await create_todo(client, token_a, title="User A Exclusive Todo")

    response = await client.get(
        "/api/v1/todos",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    titles = [item["title"] for item in items]
    assert "User A Exclusive Todo" not in titles


