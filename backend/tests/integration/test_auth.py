"""Auth integration: register lockout, login, me, logout, rate limit."""
from __future__ import annotations


def test_register_when_empty_succeeds(app_client):
    r = app_client.client.post("/auth/register", json={
        "username": "firstadmin", "password": "password123",
        "confirm_password": "password123",
    })
    assert r.status_code == 200
    assert r.json()["access_token"]


def test_register_after_admin_exists_locks_out(app_client):
    c = app_client.client
    c.post("/auth/register", json={
        "username": "firstadmin", "password": "password123",
        "confirm_password": "password123",
    })
    r = c.post("/auth/register", json={
        "username": "seconduser", "password": "password123",
        "confirm_password": "password123",
    })
    # THE load-bearing lockout: untested anywhere before this.
    assert r.status_code == 409


def test_register_password_mismatch(app_client):
    r = app_client.client.post("/auth/register", json={
        "username": "someone", "password": "password123",
        "confirm_password": "different123",
    })
    assert r.status_code == 400


def test_login_success_and_me(app_client):
    c = app_client.client
    c.post("/auth/register", json={
        "username": "firstadmin", "password": "password123",
        "confirm_password": "password123",
    })
    r = c.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "firstadmin"


def test_login_bad_password(app_client):
    c = app_client.client
    c.post("/auth/register", json={
        "username": "firstadmin", "password": "password123",
        "confirm_password": "password123",
    })
    r = c.post("/auth/login", json={"username": "firstadmin", "password": "wrongpass99"})
    assert r.status_code == 401


def test_login_rate_limit_429(app_client):
    c = app_client.client
    for _ in range(5):
        c.post("/auth/login", json={"username": "x", "password": "wrongpass99"})
    r = c.post("/auth/login", json={"username": "x", "password": "wrongpass99"})
    assert r.status_code == 429


def test_me_requires_auth(app_client):
    r = app_client.client.get("/auth/me")
    assert r.status_code == 401


class TestCookieHandling:
    """Edge cases around httpOnly cookie auth."""

    def test_login_sets_cookie(self, app_client):
        """Successful login sets epsilon_token cookie."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        r = c.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
        assert r.status_code == 200
        cookies = r.cookies
        assert "epsilon_token" in cookies
        assert cookies["epsilon_token"] is not None

    def test_logout_clears_cookie(self, app_client):
        """Logout clears the epsilon_token cookie."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        c.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
        r = c.post("/auth/logout")
        assert r.status_code == 200
        # Cookie should be cleared (empty or expired)
        cookies = r.cookies
        # httpx clears by setting empty value
        assert cookies.get("epsilon_token") == "" or "epsilon_token" not in cookies

    def test_cookie_auth_without_header(self, app_client):
        """Cookie is used for auth when no Authorization header."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        c.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
        # Use the session cookie for /me (no explicit header)
        me = c.get("/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "firstadmin"

    def test_header_takes_precedence_over_cookie(self, app_client):
        """Authorization header takes precedence over cookie."""
        c = app_client.client
        # Register and login as admin1
        c.post("/auth/register", json={
            "username": "admin1", "password": "password123",
            "confirm_password": "password123",
        })
        c.post("/auth/login", json={"username": "admin1", "password": "password123"})

        # Cookie is set for admin1
        me_with_cookie = c.get("/auth/me")
        assert me_with_cookie.json()["username"] == "admin1"

        # Now use an invalid token in header (should override cookie and fail)
        me_with_bad_header = c.get("/auth/me", headers={"Authorization": "Bearer invalid_token"})
        assert me_with_bad_header.status_code == 401  # Header is used, not cookie

    def test_cookie_is_httponly(self, app_client):
        """Cookie is set with httpOnly flag (cannot be read by JS)."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        r = c.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
        # httpx TestClient exposes cookie jar, but we check the raw Set-Cookie
        set_cookie = r.headers.get("set-cookie", "")
        assert "httponly" in set_cookie.lower()

    def test_cookie_samesite_strict(self, app_client):
        """Cookie is set with SameSite=strict."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        r = c.post("/auth/login", json={"username": "firstadmin", "password": "password123"})
        set_cookie = r.headers.get("set-cookie", "")
        assert "samesite=strict" in set_cookie.lower()

    def test_invalid_cookie_rejected(self, app_client):
        """Invalid cookie value returns 401."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        # Manually set invalid cookie
        c.cookies.set("epsilon_token", "invalid_token_value")
        me = c.get("/auth/me")
        assert me.status_code == 401

    def test_expired_cookie_rejected(self, app_client):
        """Expired JWT in cookie returns 401."""
        c = app_client.client
        c.post("/auth/register", json={
            "username": "firstadmin", "password": "password123",
            "confirm_password": "password123",
        })
        # Create an already-expired token
        from datetime import UTC, datetime, timedelta

        from jose import jwt

        from app.config import get_settings
        settings = get_settings()
        expired_payload = {
            "sub": "firstadmin",
            "uid": 1,
            "exp": datetime.now(UTC) - timedelta(hours=1)  # Expired 1 hour ago
        }
        expired_token = jwt.encode(expired_payload, settings.SECRET_KEY, algorithm="HS256")
        c.cookies.set("epsilon_token", expired_token)
        me = c.get("/auth/me")
        assert me.status_code == 401
