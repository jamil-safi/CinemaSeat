from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    hold_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    hold_token: Mapped[str] = mapped_column(String(36))
    user_ref: Mapped[str] = mapped_column(String(100), index=True)
    showtime_id: Mapped[int] = mapped_column(index=True)
    seat_id: Mapped[int] = mapped_column(index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(30), index=True)
    payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Reservation(Base):
    __tablename__ = "reservations"
    id: Mapped[int] = mapped_column(primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(36), unique=True)
    showtime_id: Mapped[int] = mapped_column(index=True)
    seat_id: Mapped[int] = mapped_column(index=True)
    __table_args__ = (
        UniqueConstraint("showtime_id", "seat_id", name="uq_confirmed_showtime_seat"),
        Index("ix_reservation_showtime", "showtime_id"),
    )


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    booking_ref: Mapped[str] = mapped_column(String(36), index=True)
    payment_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

