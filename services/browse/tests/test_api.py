import asyncio

import httpx

from app.main import app


def request(path: str) -> httpx.Response:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get(path)

    return asyncio.run(run())


def test_liveness() -> None:
    response = request("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_pagination_validation() -> None:
    assert request("/api/v1/movies?limit=0").status_code == 422

