from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class OTPRecord(Base):
    __tablename__ = "otp_records"
    booking_ref: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone: Mapped[str] = mapped_column(String(30))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    external_payment_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    booking_ref: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GatewayEvent(Base):
    __tablename__ = "gateway_events"
    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    payment_id: Mapped[str] = mapped_column(String(100))
    booking_ref: Mapped[str] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

