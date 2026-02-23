from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_db as app_get_db
from app.db.base import Base
from app.main import app


engine = create_engine("sqlite:///:memory:")
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
app.dependency_overrides[app_get_db] = override_get_db
client = TestClient(app)


def test_full_wishlist_flow() -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "user@example.com",
            "password": "password123",
            "name": "Test User",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "user@example.com", "password": "password123"},
    )
    assert login_response.status_code == 200
    login_data = login_response.json()
    token = login_data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["email"] == "user@example.com"
    assert me["name"] == "Test User"

    friend_register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "friend@example.com",
            "password": "password123",
            "name": "Friend User",
        },
    )
    assert friend_register_response.status_code == 201

    add_friend_response = client.post(
        "/api/v1/friends/",
        json={"email": "friend@example.com"},
        headers=headers,
    )
    assert add_friend_response.status_code == 201
    friend_payload = add_friend_response.json()
    assert friend_payload["friend_email"] == "friend@example.com"

    wishlist_response = client.post(
        "/api/v1/wishlists/",
        json={"title": "Birthday", "description": "Party gifts", "is_public": True},
        headers=headers,
    )
    assert wishlist_response.status_code == 201
    wishlist = wishlist_response.json()
    wishlist_id = wishlist["id"]

    item_response = client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={
            "title": "Camera",
            "description": None,
            "url": None,
            "image_url": None,
            "price": 1000.0,
            "currency": "RUB",
        },
        headers=headers,
    )
    assert item_response.status_code == 201
    item = item_response.json()
    item_id = item["id"]

    public_wishlist_response = client.get(
        f"/api/v1/public/wishlists/{wishlist['share_slug']}",
    )
    assert public_wishlist_response.status_code == 200

    public_items_response = client.get(
        f"/api/v1/public/wishlists/{wishlist['share_slug']}/items",
    )
    assert public_items_response.status_code == 200
    public_items = public_items_response.json()
    assert len(public_items) == 1

    reserve_response = client.post(
        f"/api/v1/public/wishlists/{wishlist['share_slug']}/items/{item_id}/reserve",
        json={"display_name": "Friend", "contact": "friend@example.com"},
    )
    assert reserve_response.status_code == 201

    contribution_response = client.post(
        f"/api/v1/public/wishlists/{wishlist['share_slug']}/items/{item_id}/contributions",
        json={"display_name": "Another Friend", "contact": None, "amount": 500.0},
    )
    assert contribution_response.status_code == 201

    owner_items_response = client.get(
        f"/api/v1/wishlists/{wishlist_id}/items",
        headers=headers,
    )
    assert owner_items_response.status_code == 200
    owner_items = owner_items_response.json()
    assert len(owner_items) == 1
    owner_item = owner_items[0]
    assert owner_item["is_reserved"] is True
    assert owner_item["collected_amount"] == 500.0
    assert owner_item["contributions_count"] == 1


def test_wishlists_are_isolated_between_users() -> None:
  register_response = client.post(
      "/api/v1/auth/register",
      json={
          "email": "user_a@example.com",
          "password": "password123",
          "name": "User A",
      },
  )
  assert register_response.status_code == 201

  login_response = client.post(
      "/api/v1/auth/login",
      data={"username": "user_a@example.com", "password": "password123"},
  )
  assert login_response.status_code == 200
  token_a = login_response.json()["access_token"]
  headers_a = {"Authorization": f"Bearer {token_a}"}

  wishlist_response = client.post(
      "/api/v1/wishlists/",
      json={"title": "Private A", "description": None, "is_public": False},
      headers=headers_a,
  )
  assert wishlist_response.status_code == 201

  list_response_a = client.get("/api/v1/wishlists/", headers=headers_a)
  assert list_response_a.status_code == 200
  wishlists_a = list_response_a.json()
  assert any(w["title"] == "Private A" for w in wishlists_a)

  register_b_response = client.post(
      "/api/v1/auth/register",
      json={
          "email": "user_b@example.com",
          "password": "password123",
          "name": "User B",
      },
  )
  assert register_b_response.status_code == 201

  login_b_response = client.post(
      "/api/v1/auth/login",
      data={"username": "user_b@example.com", "password": "password123"},
  )
  assert login_b_response.status_code == 200
  token_b = login_b_response.json()["access_token"]
  headers_b = {"Authorization": f"Bearer {token_b}"}

  list_response_b = client.get("/api/v1/wishlists/", headers=headers_b)
  assert list_response_b.status_code == 200
  wishlists_b = list_response_b.json()
  assert all(w["title"] != "Private A" for w in wishlists_b)


def test_register_requires_non_empty_name() -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "noname@example.com",
            "password": "password123",
            "name": "",
        },
    )
    assert response.status_code == 422

    response_spaces = client.post(
        "/api/v1/auth/register",
        json={
            "email": "spaces@example.com",
            "password": "password123",
            "name": "   ",
        },
    )
    assert response_spaces.status_code == 422


def test_realtime_item_updates_over_websocket() -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@example.com",
            "password": "password123",
            "name": "Owner",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "owner@example.com", "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    wishlist_response = client.post(
        "/api/v1/wishlists/",
        json={"title": "WS List", "description": None, "is_public": True},
        headers=headers,
    )
    assert wishlist_response.status_code == 201
    wishlist = wishlist_response.json()
    wishlist_id = wishlist["id"]

    item_response = client.post(
        f"/api/v1/wishlists/{wishlist_id}/items",
        json={
            "title": "First",
            "description": None,
            "url": None,
            "image_url": None,
            "price": None,
            "currency": None,
        },
        headers=headers,
    )
    assert item_response.status_code == 201

    with client.websocket_connect(f"/ws/wishlists/{wishlist['share_slug']}") as websocket:
        # Create a new item and expect ITEM_UPDATED
        second_item_response = client.post(
            f"/api/v1/wishlists/{wishlist_id}/items",
            json={
                "title": "Second",
                "description": None,
                "url": None,
                "image_url": None,
                "price": None,
                "currency": None,
            },
            headers=headers,
        )
        assert second_item_response.status_code == 201
        second_item = second_item_response.json()

        message = websocket.receive_json()
        assert message["type"] == "ITEM_UPDATED"
        assert message["item"]["id"] == second_item["id"]
        assert message["item"]["is_deleted"] is False

        # Delete the item and expect ITEM_UPDATED with is_deleted=True
        delete_response = client.delete(
            f"/api/v1/wishlists/{wishlist_id}/items/{second_item['id']}",
            headers=headers,
        )
        assert delete_response.status_code == 204

        delete_message = websocket.receive_json()
        assert delete_message["type"] == "ITEM_UPDATED"
        assert delete_message["item"]["id"] == second_item["id"]
        assert delete_message["item"]["is_deleted"] is True
