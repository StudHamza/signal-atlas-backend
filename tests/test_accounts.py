''' Account by Device '''

def test_account_by_device_exists(client, test_user, sample_device_id):
    user_id, headers = test_user
    # Register a device first via the JWT-protected endpoint
    client.post(
        "/api/users/me/devices",
        json={"device_id": sample_device_id},
        headers=headers,
    )

    resp = client.post(
        "/api/account/by-device",
        json={"device_id": sample_device_id},
    )

    assert resp.status_code == 200
    body = resp.json()

    assert body["account_exists"] is True
    assert body["profile"]["username"] == "testuser"

def test_account_by_device_not_found(client):
    resp = client.post(
        "/api/account/by-device",
        json={"device_id": "nonexistent"},
    )

    assert resp.status_code == 200
    assert resp.json()["account_exists"] is False


''' Profile — requires JWT auth '''

def test_get_profile(client, test_user):
    user_id, headers = test_user

    resp = client.get(f"/api/profile/{user_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()

    assert body["username"] == "testuser"

def test_get_profile_not_found(client, test_user):
    _, headers = test_user
    resp = client.get("/api/profile/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 403

def test_get_profile_forbidden(client, test_user):
    user_id, headers = test_user
    other_id = "00000000-0000-0000-0000-000000000001"
    resp = client.get(f"/api/profile/{other_id}", headers=headers)
    assert resp.status_code == 403


''' Update Profile (username) — requires JWT auth '''

def test_update_username_success(client, test_user):
    user_id, headers = test_user

    resp = client.patch(
        f"/api/profile/{user_id}",
        json={"username": "newname"},
        headers=headers,
    )

    assert resp.status_code == 200
    assert resp.json()["username"] == "newname"


''' Wallet Details — requires JWT auth '''

def test_wallet_details(client, test_user):
    user_id, headers = test_user

    resp = client.get(f"/api/wallet/{user_id}", headers=headers)

    assert resp.status_code == 200
    body = resp.json()

    assert "credits" in body
    assert "transaction_count" in body

def test_wallet_details_forbidden(client, test_user):
    _, headers = test_user
    other_id = "00000000-0000-0000-0000-000000000001"
    resp = client.get(f"/api/wallet/{other_id}", headers=headers)
    assert resp.status_code == 403


''' Wallet transactions — requires JWT auth '''

def test_wallet_transactions_empty(client, test_user):
    user_id, headers = test_user

    resp = client.get(f"/api/wallet/{user_id}/transactions", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["transactions"] == []

def test_wallet_transactions_forbidden(client, test_user):
    _, headers = test_user
    other_id = "00000000-0000-0000-0000-000000000001"
    resp = client.get(f"/api/wallet/{other_id}/transactions", headers=headers)
    assert resp.status_code == 403

def test_wallet_transactions_limit_validation(client, test_user):
    user_id, headers = test_user

    resp = client.get(
        f"/api/wallet/{user_id}/transactions?limit=1000",
        headers=headers,
    )

    assert resp.status_code == 422
