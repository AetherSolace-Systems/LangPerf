async def test_mode_endpoint_reports_single_user_when_fresh(client):
    r = await client.get("/api/auth/mode")
    assert r.status_code == 200
    assert r.json() == {"mode": "single_user"}


async def test_signup_bootstrap_creates_first_user_and_org(client):
    r = await client.post(
        "/api/auth/signup",
        json={"email": "andrew@example.com", "password": "correcthorsebatterystaple", "display_name": "Andrew"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["user"]["email"] == "andrew@example.com"
    assert body["user"]["is_admin"] is True
    cookie = r.cookies.get("langperf_session")
    assert cookie is not None


async def test_signup_rejected_when_user_exists_without_admin_auth(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.post(
        "/api/auth/signup",
        json={"email": "c@d", "password": "pw12345678", "display_name": "C"},
    )
    assert r.status_code == 403


async def test_login_sets_session_cookie(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": "a@b", "password": "pw12345678"},
    )
    assert r.status_code == 200
    assert r.cookies.get("langperf_session")


async def test_login_rejects_wrong_password(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.post(
        "/api/auth/login",
        json={"email": "a@b", "password": "wrong"},
    )
    assert r.status_code == 401


async def test_me_returns_current_user(client):
    await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    r = await client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["user"]["email"] == "a@b"


async def test_logout_clears_session(client):
    signup = await client.post(
        "/api/auth/signup",
        json={"email": "a@b", "password": "pw12345678", "display_name": "A"},
    )
    token = signup.cookies["langperf_session"]
    r = await client.post("/api/auth/logout", cookies={"langperf_session": token})
    assert r.status_code == 204
