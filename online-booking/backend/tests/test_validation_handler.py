"""Tests for custom validation error handlers (P1-1).

Regression: @app.exception_handler(422) never fired for real request
validation errors — Starlette dispatches RequestValidationError by class,
not by status code, so responses fell back to the default FastAPI format.
"""


class TestValidationHandler:
    async def test_register_invalid_body_uses_custom_format(self, client):
        """Invalid body -> 422 with friendly 'loc: msg' strings (not default dicts)."""
        resp = await client.post("/api/v1/auth/register", json={"email": "not-an-email"})
        assert resp.status_code == 422
        data = resp.json()
        assert isinstance(data["detail"], list)
        assert data["detail"], "detail must not be empty"
        for item in data["detail"]:
            assert isinstance(item, str)
            assert " -> " in item  # custom "loc: msg" format

    async def test_register_missing_fields_mentions_loc(self, client):
        """Missing required fields are reported with their location."""
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422
        joined = " ".join(resp.json()["detail"])
        assert "body" in joined
