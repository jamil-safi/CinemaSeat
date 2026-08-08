import asyncio

import httpx

from app.main import app


def test_liveness_does_not_check_gateway() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health/live")

    response = asyncio.run(run())
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_internal_endpoint_requires_token() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/internal/v1/otp/example/verified")

    assert asyncio.run(run()).status_code == 422

