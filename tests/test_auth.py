""" Auth tests — new backend API auth (mocked Supabase). """

from unittest.mock import patch


def test_register_validation_error(client):
    """Missing fields should return 422."""
    resp = client.post("/api/auth/register", json={})
    assert resp.status_code == 422


@patch("app.routers.auth._call_supabase")
def test_login_validation_error(mock_call, client):
    """Missing fields should return 422."""
    resp = client.post("/api/auth/login", json={})
    assert resp.status_code == 422
