import json
from unittest.mock import MagicMock

from fastapi import Request

from app.main import _unhandled_exception_handler


def _mock_request(path: str = "/test") -> Request:
    req = MagicMock(spec=Request)
    req.state = MagicMock(request_id="test-id")
    req.method = "GET"
    req.url.path = path
    return req


async def test_unhandled_exception_returns_500():
    response = await _unhandled_exception_handler(
        _mock_request(), RuntimeError("something went wrong")
    )

    assert response.status_code == 500


async def test_error_response_body_has_no_stack_trace():
    response = await _unhandled_exception_handler(
        _mock_request(), RuntimeError("secret internal detail")
    )

    body = json.loads(response.body)
    assert body == {"detail": "Internal server error"}
    assert "secret internal detail" not in response.body.decode()
    assert "Traceback" not in response.body.decode()
