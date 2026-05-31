def test_login_success(client):
    # create a user first
    created = client.post(
        "/api/account/create",
        json={"username": "testuser"},
    ).json()

    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser"},
    )

    assert resp.status_code == 200
    body = resp.json()

    assert "profile" in body
    assert "id" in body["profile"]
    assert body["profile"]["username"] == "testuser"
    assert "credits" in body["profile"]
    assert "device_ids" in body["profile"]

def test_login_user_not_found(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "does_not_exist"},
    )

    assert resp.status_code == 404
    assert "detail" in resp.json()

def test_login_username_too_short(client):
    resp = client.post(
        "/api/auth/login",
        json={"username": "ab"},  # min_length=3
    )

    assert resp.status_code == 422

def test_login_missing_username(client):
    resp = client.post(
        "/api/auth/login",
        json={},
    )

    assert resp.status_code == 422

def test_login_username_case_sensitivity(client):
    client.post(
        "/api/account/create",
        json={"username": "TestUser"},
    )

    resp = client.post(
        "/api/auth/login",
        json={"username": "testuser"},
    )

    # depends on design: currently this should fail
    assert resp.status_code == 404
