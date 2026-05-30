''' Account by Device '''
def test_account_by_device_exists(client, sample_profile, sample_device_id):
    # create profile + device first
    client.post(
        "/api/account/create",
        json={
            "username": sample_profile["username"],
            "device_id": sample_device_id,
        },
    )

    resp = client.post(
        "/api/account/by-device",
        json={"device_id": sample_device_id},
    )

    assert resp.status_code == 200
    body = resp.json()

    assert body["account_exists"] is True
    assert body["profile"]["username"] == sample_profile["username"]
    assert sample_device_id in body["profile"]["device_ids"]

def test_account_by_device_not_found(client):
    resp = client.post(
        "/api/account/by-device",
        json={"device_id": "nonexistent"},
    )

    assert resp.status_code == 200
    assert resp.json()["account_exists"] is False

''' Create Account '''

def test_create_account_without_device(client):
    resp = client.post(
        "/api/account/create",
        json={"username": "user1"},
    )

    assert resp.status_code == 200
    body = resp.json()

    assert body["username"] == "user1"
    assert body["device_ids"] == []

def test_create_account_with_device(client):
    resp = client.post(
        "/api/account/create",
        json={
            "username": "user2",
            "device_id": "abc123",
        },
    )

    assert resp.status_code == 200
    body = resp.json()

    assert "abc123" in body["device_ids"]

def test_create_account_duplicate_username(client):
    client.post(
        "/api/account/create",
        json={"username": "duplicate"},
    )

    resp = client.post(
        "/api/account/create",
        json={"username": "duplicate"},
    )

    assert resp.status_code == 409

def test_create_account_device_already_linked(client):
    client.post(
        "/api/account/create",
        json={
            "username": "user1",
            "device_id": "shared-device",
        },
    )

    resp = client.post(
        "/api/account/create",
        json={
            "username": "user2",
            "device_id": "shared-device",
        },
    )

    assert resp.status_code == 409

''' Register Device '''

def test_register_device_success(client, sample_profile):
    profile_resp = client.post(
        "/api/account/create",
        json={"username": "user1"},
    )

    user_id = profile_resp.json()["id"]

    resp = client.post(
        "/api/devices/register",
        json={
            "user_id": user_id,
            "device_id": "device-123",
        },
    )

    assert resp.status_code == 200
    body = resp.json()

    assert body["device_id"] == "device-123"
    assert body["user_id"] == user_id

def test_register_device_profile_not_found(client):
    resp = client.post(
        "/api/devices/register",
        json={
            "user_id": "fake-id",
            "device_id": "abc",
        },
    )

    assert resp.status_code == 404

def test_register_device_conflict(client):
    profile = client.post(
        "/api/account/create",
        json={"username": "user1"},
    ).json()

    profile2 = client.post(
        "/api/account/create",
        json={"username": "user2"},
    ).json()

    client.post(
        "/api/devices/register",
        json={
            "user_id": profile["id"],
            "device_id": "shared-device",
        },
    )

    resp = client.post(
        "/api/devices/register",
        json={
            "user_id": profile2["id"],
            "device_id": "shared-device",
        },
    )

    assert resp.status_code == 409

''' Get profile '''

def test_get_profile(client):
    created = client.post(
        "/api/account/create",
        json={
            "username": "user1",
            "device_id": "abc123",
        },
    ).json()

    resp = client.get(f"/api/profile/{created['id']}")

    assert resp.status_code == 200
    body = resp.json()

    assert body["username"] == "user1"
    assert "abc123" in body["device_ids"]

def test_get_profile_not_found(client):
    resp = client.get("/api/profile/does-not-exist")
    assert resp.status_code == 404

''' Update Profile (username) '''

def test_update_username_success(client):
    profile = client.post(
        "/api/account/create",
        json={"username": "oldname"},
    ).json()

    resp = client.patch(
        f"/api/profile/{profile['id']}",
        json={"username": "newname"},
    )

    assert resp.status_code == 200
    assert resp.json()["username"] == "newname"

def test_update_username_conflict(client):
    p1 = client.post(
        "/api/account/create",
        json={"username": "user1"},
    ).json()

    client.post(
        "/api/account/create",
        json={"username": "user2"},
    )

    resp = client.patch(
        f"/api/profile/{p1['id']}",
        json={"username": "user2"},
    )

    assert resp.status_code == 409

''' Wallet Details '''

def test_wallet_details(client):
    profile = client.post(
        "/api/account/create",
        json={"username": "walletuser"},
    ).json()

    resp = client.get(f"/api/wallet/{profile['id']}")

    assert resp.status_code == 200
    body = resp.json()

    assert "credits" in body
    assert "transaction_count" in body

''' Wallet transactions '''

def test_wallet_transactions_empty(client):
    profile = client.post(
        "/api/account/create",
        json={"username": "walletuser"},
    ).json()

    resp = client.get(
        f"/api/wallet/{profile['id']}/transactions"
    )

    assert resp.status_code == 200
    assert resp.json()["transactions"] == []

def test_wallet_transactions_limit(client):
    profile = client.post(
        "/api/account/create",
        json={"username": "walletuser"},
    ).json()

    resp = client.get(
        f"/api/wallet/{profile['id']}/transactions?limit=10"
    )

    assert resp.status_code == 200
    assert len(resp.json()["transactions"]) <= 10

def test_wallet_transactions_limit_validation(client):
    profile = client.post(
        "/api/account/create",
        json={"username": "walletuser"},
    ).json()

    resp = client.get(
        f"/api/wallet/{profile['id']}/transactions?limit=1000"
    )

    assert resp.status_code == 422
