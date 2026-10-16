from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel

from src.app.error_handlers import register_error_handlers
from src.shared.enums.error_code import ErrorCode
from src.shared.errors.app_error import AppError

FIXED_NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)


class Payload(BaseModel):
    amount: int


def build_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app, now=lambda: FIXED_NOW)

    @app.get("/business-rule")
    def business_rule():
        raise AppError(status_code=422, error_code=ErrorCode.VALIDATION_ERROR, message="regla de negocio")

    @app.get("/explode")
    def explode():
        raise ZeroDivisionError("secret internal detail")

    @app.post("/payload")
    def payload(body: Payload):
        return body

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def client() -> TestClient:
    return build_client()


def test_app_error_uses_standard_format(client: TestClient):
    response = client.get("/business-rule")
    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "statusCode": 422,
        "errorCode": "VALIDATION_ERROR",
        "message": "regla de negocio",
        "timestamp": "2026-10-16T12:00:00Z",
        "path": "/business-rule",
    }


def test_unhandled_error_hides_internal_detail(client: TestClient):
    response = client.get("/explode")
    body = response.json()
    assert response.status_code == 500
    assert body["errorCode"] == "INTERNAL_ERROR"
    assert "secret" not in response.text
    assert "Traceback" not in response.text


def test_unknown_route_uses_standard_format(client: TestClient):
    response = client.get("/nope")
    body = response.json()
    assert response.status_code == 404
    assert body["errorCode"] == "NOT_FOUND"
    assert body["success"] is False


def test_request_validation_error_lists_details(client: TestClient):
    response = client.post("/payload", json={"amount": "abc"})
    body = response.json()
    assert response.status_code == 400
    assert body["errorCode"] == "VALIDATION_ERROR"
    assert body["details"][0]["path"] == "body.amount"
    assert body["details"][0]["message"]
