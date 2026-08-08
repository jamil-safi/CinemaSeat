import os
from contextlib import asynccontextmanager
from uuid import uuid4

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, SessionLocal, engine, get_session
from .models import GatewayEvent, OTPRecord, Payment

GATEWAY_URL = os.getenv("GATEWAY_BASE_URL", "http://localhost:9000")
BOOKING_URL = os.getenv("BOOKING_SERVICE_URL", "http://localhost:8001")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8080")
INTERNAL_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "change-me")
TERMINAL = {"SUCCEEDED", "FAILED", "REFUNDED"}


class OTPSend(BaseModel):
    booking_ref: str
    phone: str = Field(min_length=5, max_length=30)


class OTPVerify(BaseModel):
    booking_ref: str
    code: str = Field(min_length=1, max_length=20)


class PaymentRequest(BaseModel):
    booking_ref: str
    amount: float = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)


class RefundRequest(BaseModel):
    payment_id: str
    booking_ref: str


class CallbackBody(BaseModel):
    event_id: str
    payment_id: str
    booking_ref: str
    status: str
    amount: float


def require_internal(token: str) -> None:
    if token != INTERNAL_TOKEN:
        raise HTTPException(403, "forbidden")


async def submit_charge(
    local_payment_id: str, mock_force: str | None, mock_mode: str | None
) -> None:
    headers: dict[str, str] = {}
    if mock_force:
        headers["X-Mock-Force"] = mock_force
    if mock_mode:
        headers["X-Mock-Mode"] = mock_mode
    async with SessionLocal() as session:
        payment = await session.scalar(select(Payment).where(Payment.payment_id == local_payment_id))
        if not payment:
            return
        payment.status = "SUBMITTING"
        await session.commit()
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{GATEWAY_URL}/charge",
                    headers=headers,
                    json={
                        "amount": float(payment.amount),
                        "currency": payment.currency,
                        "booking_ref": payment.booking_ref,
                        "callback_url": f"{PUBLIC_BASE_URL}/api/v1/payments/gateway/callback",
                    },
                )
            response.raise_for_status()
            payload = response.json()
            await session.refresh(payment)
            if payment.status not in TERMINAL:
                payment.external_payment_id = payload.get("payment_id")
                payment.status = payload.get("status", "PENDING")
        except (httpx.HTTPError, ValueError):
            await session.refresh(payment)
            if payment.status not in TERMINAL:
                payment.status = "UNKNOWN"
        await session.commit()


async def deliver_event(payload: dict) -> None:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            await client.post(
                f"{BOOKING_URL}/internal/v1/payment-events",
                headers={"X-Internal-Token": INTERNAL_TOKEN},
                json=payload,
            )
    except httpx.HTTPError:
        return


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="CinemaSeat Payment Service", lifespan=lifespan)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.post("/api/v1/otp/send", status_code=status.HTTP_202_ACCEPTED)
async def send_otp(body: OTPSend, session: AsyncSession = Depends(get_session)) -> dict:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(
                f"{GATEWAY_URL}/otp/send", json={"phone": body.phone, "ref": body.booking_ref}
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "OTP gateway unavailable") from exc
    if response.status_code != 202:
        raise HTTPException(503, "OTP could not be sent")
    await session.execute(
        pg_insert(OTPRecord)
        .values(booking_ref=body.booking_ref, phone=body.phone, verified=False)
        .on_conflict_do_update(
            index_elements=["booking_ref"], set_={"phone": body.phone, "verified": False}
        )
    )
    await session.commit()
    return {"status": "PENDING", "booking_ref": body.booking_ref}


@app.post("/api/v1/otp/verify")
async def verify_otp(body: OTPVerify, session: AsyncSession = Depends(get_session)) -> dict:
    record = await session.get(OTPRecord, body.booking_ref)
    if not record:
        raise HTTPException(404, "OTP request not found")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(
                f"{GATEWAY_URL}/otp/verify", json={"ref": body.booking_ref, "code": body.code}
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "OTP gateway unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(400, "invalid OTP")
    record.verified = True
    await session.commit()
    return {"verified": True, "booking_ref": body.booking_ref}


@app.get("/internal/v1/otp/{booking_ref}/verified")
async def otp_status(
    booking_ref: str,
    x_internal_token: str = Header(alias="X-Internal-Token"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    require_internal(x_internal_token)
    record = await session.get(OTPRecord, booking_ref)
    return {"verified": bool(record and record.verified)}


@app.post("/internal/v1/payments", status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    body: PaymentRequest,
    background_tasks: BackgroundTasks,
    x_internal_token: str = Header(alias="X-Internal-Token"),
    x_mock_force: str | None = Header(None, alias="X-Mock-Force"),
    x_mock_mode: str | None = Header(None, alias="X-Mock-Mode"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    require_internal(x_internal_token)
    existing = await session.scalar(select(Payment).where(Payment.booking_ref == body.booking_ref))
    if existing:
        return {"payment_id": existing.payment_id, "status": existing.status}
    payment_id = str(uuid4())
    session.add(
        Payment(
            payment_id=payment_id,
            booking_ref=body.booking_ref,
            amount=body.amount,
            currency=body.currency.upper(),
            status="CREATED",
        )
    )
    await session.commit()
    background_tasks.add_task(submit_charge, payment_id, x_mock_force, x_mock_mode)
    return {"payment_id": payment_id, "status": "CREATED"}


@app.post("/api/v1/payments/gateway/callback")
async def gateway_callback(
    body: CallbackBody,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> dict:
    inserted = await session.scalar(
        pg_insert(GatewayEvent)
        .values(**body.model_dump())
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(GatewayEvent.event_id)
    )
    if not inserted:
        await session.rollback()
        return {"status": "duplicate"}
    payment = await session.scalar(select(Payment).where(Payment.booking_ref == body.booking_ref))
    if payment:
        payment.external_payment_id = body.payment_id
        payment.status = body.status
    await session.commit()
    background_tasks.add_task(deliver_event, body.model_dump())
    return {"status": "accepted"}


@app.post("/internal/v1/refunds", status_code=status.HTTP_202_ACCEPTED)
async def refund(
    body: RefundRequest,
    x_internal_token: str = Header(alias="X-Internal-Token"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    require_internal(x_internal_token)
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.post(f"{GATEWAY_URL}/refund", json={"payment_id": body.payment_id})
    except httpx.HTTPError as exc:
        raise HTTPException(503, "refund gateway unavailable") from exc
    if response.status_code != 202:
        raise HTTPException(503, "refund could not be started")
    payment = await session.scalar(select(Payment).where(Payment.booking_ref == body.booking_ref))
    if payment:
        payment.status = "REFUND_PENDING"
        await session.commit()
    return {"status": "PENDING"}

