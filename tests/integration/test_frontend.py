import os
import re

import httpx


BASE_URL = os.getenv("BASE_URL", "http://localhost:8080")


def test_frontend_and_catalog_are_available_from_the_same_origin() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=5) as client:
        page = client.get("/")
        movies = client.get("/api/v1/movies")
        theatres = client.get("/api/v1/theatres")
        showtimes = client.get("/api/v1/showtimes")

    assert page.status_code == 200
    assert "CinemaSeat" in page.text
    script_path = re.search(r'<script[^>]+src="([^"]+\.js)"', page.text).group(1)
    script = httpx.get(f"{BASE_URL}{script_path}", timeout=5)
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "/api/v1" in script.text

    assert movies.status_code == 200
    assert theatres.status_code == 200
    assert showtimes.status_code == 200
    assert movies.json()
    assert theatres.json()
    assert showtimes.json()


def test_frontend_showtime_can_load_the_booking_seat_map() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=5) as client:
        showtimes = client.get("/api/v1/showtimes")
        showtimes.raise_for_status()
        showtime_id = showtimes.json()[0]["id"]
        seat_map = client.get(f"/api/v1/showtimes/{showtime_id}/seats")

    assert seat_map.status_code == 200
    assert seat_map.json()["showtime_id"] == showtime_id
    assert seat_map.json()["seats"]
