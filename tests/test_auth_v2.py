import json
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


def create_test_app(tmp_dir: Path) -> TestClient:
    # Point V2 auth at an isolated data directory
    os.environ["V2_DATA_DIR"] = str(tmp_dir)

    # Import after setting env so service uses this directory
    from web_v2.auth_routes import router as auth_router

    app = FastAPI()
    app.include_router(auth_router)
    return TestClient(app)


def test_register_and_login_flow(tmp_path: Path):
    client = create_test_app(tmp_path)

    # Register new user
    email = "user1@example.com"
    password = "password123"
    res = client.post(
        "/v2/auth/register", data={"email": email, "password": password}
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert "token" in body
    assert body["user"]["email"] == email
    assert body["user"]["role"] == "user"

    # Session cookie should be set and used for /me
    res_me = client.get("/v2/auth/me")
    assert res_me.status_code == 200, res_me.text
    me = res_me.json()
    assert me["email"] == email


def test_invalid_login(tmp_path: Path):
    client = create_test_app(tmp_path)

    # Seeded admin exists, but we try wrong password
    res = client.post(
        "/v2/auth/login",
        data={"email": "admin@instaforge.com", "password": "wrong-password"},
    )
    assert res.status_code == 401


def test_token_expiry(tmp_path: Path):
    client = create_test_app(tmp_path)

    from src_v2.auth import service as auth_service

    # Create and login a user
    email = "expire@example.com"
    password = "password123"
    res = client.post(
        "/v2/auth/register", data={"email": email, "password": password}
    )
    assert res.status_code == 201, res.text

    # Manually expire all sessions by editing the sessions file
    sessions_file = Path(os.environ["V2_DATA_DIR"]) / "sessions_v2.json"
    assert sessions_file.exists()
    data = json.loads(sessions_file.read_text(encoding="utf-8"))
    for token, sess in data.get("sessions", {}).items():
        # Set expires_at to an old date
        sess["expires_at"] = "2000-01-01T00:00:00"
    sessions_file.write_text(json.dumps(data), encoding="utf-8")

    # Now /me should report unauthorized
    res_me = client.get("/v2/auth/me")
    assert res_me.status_code == 401


def test_access_control_admin_vs_user(tmp_path: Path):
    client = create_test_app(tmp_path)

    # Register a normal user
    user_email = "user2@example.com"
    user_password = "password123"
    res = client.post(
        "/v2/auth/register", data={"email": user_email, "password": user_password}
    )
    assert res.status_code == 201

    # As normal user, /users should only return themselves
    res_users = client.get("/v2/auth/users")
    assert res_users.status_code == 200
    users = res_users.json()
    assert len(users) == 1
    assert users[0]["email"] == user_email

    # Login as admin (seeded)
    # Create a fresh client so we don't reuse the normal user's cookie
    client_admin = create_test_app(tmp_path)
    res_admin_login = client_admin.post(
        "/v2/auth/login",
        data={"email": "admin@instaforge.com", "password": "admin123"},
    )
    assert res_admin_login.status_code == 200, res_admin_login.text

    # Admin should see all users (admin + user2, and possibly earlier ones)
    res_admin_users = client_admin.get("/v2/auth/users")
    assert res_admin_users.status_code == 200
    admin_users = res_admin_users.json()
    emails = {u["email"] for u in admin_users}
    assert "admin@instaforge.com" in emails
    assert user_email in emails
    assert len(admin_users) >= 2

