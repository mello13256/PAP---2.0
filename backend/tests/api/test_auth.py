from tests.conftest import register


async def test_register_logs_the_user_in(client) -> None:
    user = await register(client, "Ana@Example.com")
    assert user["email"] == "ana@example.com"  # normalizado
    assert "password" not in user and "password_hash" not in user

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]


async def test_session_cookie_is_http_only(client) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "display_name": "A", "password": "password-segura"},
    )
    cookie_header = response.headers["set-cookie"].lower()
    assert "httponly" in cookie_header
    assert "samesite=lax" in cookie_header


async def test_duplicate_email_is_rejected(client) -> None:
    await register(client)
    response = await client.post(
        "/api/auth/register",
        json={"email": "ana@example.com", "display_name": "Outra", "password": "outra-password"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_login_and_logout(make_client) -> None:
    await register(await make_client())

    browser = await make_client()
    assert (await browser.get("/api/auth/me")).status_code == 401

    login = await browser.post(
        "/api/auth/login", json={"email": "ana@example.com", "password": "password-segura"}
    )
    assert login.status_code == 200
    assert (await browser.get("/api/auth/me")).status_code == 200

    await browser.post("/api/auth/logout")
    assert (await browser.get("/api/auth/me")).status_code == 401


async def test_wrong_password_and_unknown_email_give_same_error(client) -> None:
    await register(client)
    wrong = await client.post(
        "/api/auth/login", json={"email": "ana@example.com", "password": "errada-errada"}
    )
    unknown = await client.post(
        "/api/auth/login", json={"email": "ninguem@example.com", "password": "errada-errada"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_short_password_is_a_validation_error(client) -> None:
    response = await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "display_name": "A", "password": "curta"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "password"


async def test_tampered_cookie_is_rejected(client) -> None:
    client.cookies.set("mm_session", "isto.nao.e-um-token")
    assert (await client.get("/api/auth/me")).status_code == 401
