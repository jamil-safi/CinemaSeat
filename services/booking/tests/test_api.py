import asyncio

import httpx

from app.main import app, hold_key


def test_hold_key_is_scoped_to_showtime_and_seat() -> None:
    assert hold_key(7, 12) == "hold:7:12"


def test_liveness_does_not_check_dependencies() -> None:
    async def run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.get("/health/live")

    response = asyncio.run(run())
    assert response.status_code == 200

