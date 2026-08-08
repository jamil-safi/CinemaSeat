import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import redis.asyncio as redis
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, engine, get_session
from .models import Booking, PaymentEvent, Reservation

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
BROWSE_URL = os.getenv("BROWSE_SERVICE_URL", "http://localhost:8001")
PAYMENT_URL = os.getenv("PAYMENT_SERVICE_URL", "http://localhost:8002")
INTERNAL_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "change-me")
HOLD_TTL = int(os.getenv("HOLD_TTL_SECONDS", "30"))
PAYMENT_TTL = int(os.getenv("PAYMENT_PENDING_TTL_SECONDS", "60"))

redis_client = redis.from_url(REDIS_URL, decode_responses=True)
TOKEN_DELETE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"
TOKEN_EXTEND = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end"


class HoldRequest(BaseModel):
    showtime_id: int = Field(gt=0)
    seat_id: int = Field(gt=0)
    user_ref: str = Field(min_length=1, max_length=100)


class PaymentEventBody(BaseModel):
    event_id: str
    payment_id: str
    booking_ref: str
    status: str
    amount: float | None = None


def hold_key(showtime_id: int, seat_id: int) -> str:
    return f"hold:{showtime_id}:{seat_id}"


async def layout(showtime_id: int) -> dict:
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{BROWSE_URL}/internal/v1/showtimes/{showtime_id}/seat-layout")
    except httpx.HTTPError as exc:
        raise HTTPException(503, "browse service unavailable") from exc
    if response.status_code == 404:
        raise HTTPException(404, "showtime not found")
    if response.status_code != 200:
        raise HTTPException(503, "browse service unavailable")
    return response.json()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(title="CinemaSeat Booking Service", lifespan=lifespan)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    await redis_client.ping()
    return {"status": "ready"}


@app.get("/api/v1/showtimes/{showtime_id}/seats")
async def seat_map(showtime_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    data = await layout(showtime_id)
    sold = set(
        (await session.scalars(select(Reservation.seat_id).where(Reservation.showtime_id == showtime_id))).all()
    )
    keys = [hold_key(showtime_id, seat["id"]) for seat in data["seats"]]
    held_values = await redis_client.mget(keys) if keys else []
    seats = []
    for seat, held in zip(data["seats"], held_values, strict=True):
        availability = "SOLD" if seat["id"] in sold else "HELD" if held else "AVAILABLE"
        seats.append({**seat, "status": availability})
    return {"showtime_id": showtime_id, "price": data["price"], "currency": data["currency"], "seats": seats}


@app.post("/api/v1/holds", status_code=status.HTTP_201_CREATED)
async def create_hold(body: HoldRequest, session: AsyncSession = Depends(get_session)) -> dict:
    data = await layout(body.showtime_id)
    if body.seat_id not in {seat["id"] for seat in data["seats"]}:
        raise HTTPException(404, "seat not found")
    sold = await session.scalar(
        select(Reservation.id).where(
            Reservation.showtime_id == body.showtime_id, Reservation.seat_id == body.seat_id
        )
    )
    if sold:
        raise HTTPException(409, "seat is sold")

    token, hold_id, booking_ref = str(uuid4()), str(uuid4()), str(uuid4())
    key = hold_key(body.showtime_id, body.seat_id)
    if not await redis_client.set(key, token, ex=HOLD_TTL, nx=True):
        raise HTTPException(409, "seat is already held")
    expires_at = datetime.now(UTC) + timedelta(seconds=HOLD_TTL)
    booking = Booking(
        booking_ref=booking_ref,
        hold_id=hold_id,
        hold_token=token,
        user_ref=body.user_ref,
        showtime_id=body.showtime_id,
        seat_id=body.seat_id,
        price=data["price"],
        currency=data["currency"],
        state="HELD",
        expires_at=expires_at,
    )
    session.add(booking)
    try:
        await session.commit()
    except Exception:
        await redis_client.eval(TOKEN_DELETE, 1, key, token)
        raise
    return {
        "hold_id": hold_id,
        "hold_token": token,
        "booking_ref": booking_ref,
        "state": booking.state,
        "expires_at": expires_at,
    }


@app.delete("/api/v1/holds/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_hold(
    hold_id: str,
    x_hold_token: str = Header(alias="X-Hold-Token"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    booking = await session.scalar(select(Booking).where(Booking.hold_id == hold_id))
    if not booking:
        raise HTTPException(404, "hold not found")
    if booking.hold_token != x_hold_token:
        raise HTTPException(403, "invalid hold token")
    deleted = await redis_client.eval(
        TOKEN_DELETE, 1, hold_key(booking.showtime_id, booking.seat_id), booking.hold_token
    )
    if not deleted:
        raise HTTPException(409, "hold expired or no longer owned")
    booking.state = "EXPIRED"
    await session.commit()
    return Response(status_code=204)


@app.get("/api/v1/bookings/{booking_ref}")
async def get_booking(booking_ref: str, session: AsyncSession = Depends(get_session)) -> dict:
    booking = await session.scalar(select(Booking).where(Booking.booking_ref == booking_ref))
    if not booking:
        raise HTTPException(404, "booking not found")
    if booking.state in {"HELD", "PAYMENT_PENDING"}:
        owner = await redis_client.get(hold_key(booking.showtime_id, booking.seat_id))
        if owner != booking.hold_token:
            booking.state = "EXPIRED"
            await session.commit()
    return {
        "booking_ref": booking.booking_ref,
        "showtime_id": booking.showtime_id,
        "seat_id": booking.seat_id,
        "state": booking.state,
        "price": float(booking.price),
        "currency": booking.currency,
    }


@app.post("/api/v1/bookings/{booking_ref}/pay", status_code=status.HTTP_202_ACCEPTED)
async def pay(
    booking_ref: str,
    x_mock_force: str | None = Header(None, alias="X-Mock-Force"),
    x_mock_mode: str | None = Header(None, alias="X-Mock-Mode"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    booking = await session.scalar(
        select(Booking).where(Booking.booking_ref == booking_ref).with_for_update()
    )
    if not booking:
        raise HTTPException(404, "booking not found")
    if booking.state != "HELD":
        raise HTTPException(409, "booking is not payable")
    key = hold_key(booking.showtime_id, booking.seat_id)
    if not await redis_client.eval(TOKEN_EXTEND, 1, key, booking.hold_token, PAYMENT_TTL):
        booking.state = "EXPIRED"
        await session.commit()
        raise HTTPException(409, "hold expired")

    headers = {"X-Internal-Token": INTERNAL_TOKEN}
    if x_mock_force:
        headers["X-Mock-Force"] = x_mock_force
    if x_mock_mode:
        headers["X-Mock-Mode"] = x_mock_mode
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            otp = await client.get(
                f"{PAYMENT_URL}/internal/v1/otp/{booking_ref}/verified", headers=headers
            )
            if otp.status_code != 200 or not otp.json().get("verified"):
                raise HTTPException(400, "OTP is not verified")
            response = await client.post(
                f"{PAYMENT_URL}/internal/v1/payments",
                headers=headers,
                json={
                    "booking_ref": booking_ref,
                    "amount": float(booking.price),
                    "currency": booking.currency,
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "payment service unavailable") from exc
    if response.status_code != 202:
        raise HTTPException(503, "payment could not be started")
    booking.state = "PAYMENT_PENDING"
    booking.payment_id = response.json()["payment_id"]
    booking.expires_at = datetime.now(UTC) + timedelta(seconds=PAYMENT_TTL)
    await session.commit()
    return {"booking_ref": booking_ref, "payment_id": booking.payment_id, "state": booking.state}


@app.post("/internal/v1/payment-events")
async def payment_event(
    body: PaymentEventBody,
    x_internal_token: str = Header(alias="X-Internal-Token"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if x_internal_token != INTERNAL_TOKEN:
        raise HTTPException(403, "forbidden")
    inserted = await session.scalar(
        pg_insert(PaymentEvent)
        .values(
            event_id=body.event_id,
            booking_ref=body.booking_ref,
            payment_id=body.payment_id,
            status=body.status,
        )
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(PaymentEvent.event_id)
    )
    if not inserted:
        await session.rollback()
        return {"status": "duplicate"}
    booking = await session.scalar(
        select(Booking).where(Booking.booking_ref == body.booking_ref).with_for_update()
    )
    if not booking:
        await session.commit()
        return {"status": "ignored"}

    refund = False
    key = hold_key(booking.showtime_id, booking.seat_id)
    if body.status == "SUCCEEDED":
        owner = await redis_client.get(key)
        if owner != booking.hold_token:
            booking.state = "REFUND_REQUIRED"
            refund = True
        else:
            reservation_id = await session.scalar(
                pg_insert(Reservation)
                .values(
                    booking_ref=booking.booking_ref,
                    showtime_id=booking.showtime_id,
                    seat_id=booking.seat_id,
                )
                .on_conflict_do_nothing(index_elements=["showtime_id", "seat_id"])
                .returning(Reservation.id)
            )
            if reservation_id:
                booking.state = "CONFIRMED"
                await redis_client.eval(TOKEN_DELETE, 1, key, booking.hold_token)
            else:
                booking.state = "REFUND_REQUIRED"
                refund = True
    elif body.status == "FAILED":
        booking.state = "PAYMENT_FAILED"
        await redis_client.eval(TOKEN_DELETE, 1, key, booking.hold_token)
    elif body.status == "REFUNDED":
        booking.state = "REFUNDED"
    booking.payment_id = body.payment_id
    await session.commit()

    if refund:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                await client.post(
                    f"{PAYMENT_URL}/internal/v1/refunds",
                    headers={"X-Internal-Token": INTERNAL_TOKEN},
                    json={"payment_id": body.payment_id, "booking_ref": body.booking_ref},
                )
        except httpx.HTTPError:
            pass
    return {"status": "processed", "booking_state": booking.state}

