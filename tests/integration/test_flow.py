import asyncio
import os
import time
from uuid import uuid4

import httpx

BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")


def test_same_seat_has_one_winner_and_hold_expires() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=5) as client:
        showtime = client.get("/api/v1/showtimes").json()[0]
        seat = client.get(f"/api/v1/showtimes/{showtime['id']}/seats").json()["seats"][0]

    async def hold(index: int) -> httpx.Response:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=10) as client:
            return await client.post(
                "/api/v1/holds",
                json={
                    "showtime_id": showtime["id"],
                    "seat_id": seat["id"],
                    "user_ref": f"load-user-{index}-{uuid4()}",
                },
            )

    async def race() -> list[httpx.Response]:
        return await asyncio.gather(*(hold(index) for index in range(100)))

    responses = asyncio.run(race())
    codes = [response.status_code for response in responses]
    assert codes.count(201) == 1
    assert codes.count(409) == 99

    with httpx.Client(base_url=BASE_URL, timeout=5) as client:
        seat_map = client.get(f"/api/v1/showtimes/{showtime['id']}/seats").json()
        assert next(item for item in seat_map["seats"] if item["id"] == seat["id"])["status"] == "HELD"

        second_seat = seat_map["seats"][1]
        first = client.post(
            "/api/v1/holds",
            json={"showtime_id": showtime["id"], "seat_id": second_seat["id"], "user_ref": "first"},
        )
        assert first.status_code == 201
        time.sleep(3)
        second = client.post(
            "/api/v1/holds",
            json={"showtime_id": showtime["id"], "seat_id": second_seat["id"], "user_ref": "second"},
        )
        assert second.status_code == 201
