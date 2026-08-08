from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Movie(Base):
    __tablename__ = "movies"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer)


class Theatre(Base):
    __tablename__ = "theatres"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    city: Mapped[str] = mapped_column(String(100), index=True)


class Auditorium(Base):
    __tablename__ = "auditoriums"
    id: Mapped[int] = mapped_column(primary_key=True)
    theatre_id: Mapped[int] = mapped_column(ForeignKey("theatres.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))


class Seat(Base):
    __tablename__ = "seats"
    id: Mapped[int] = mapped_column(primary_key=True)
    auditorium_id: Mapped[int] = mapped_column(ForeignKey("auditoriums.id"), index=True)
    row_label: Mapped[str] = mapped_column(String(5))
    number: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20), default="STANDARD")
    __table_args__ = (
        Index("ix_seat_auditorium_label", "auditorium_id", "row_label", "number", unique=True),
    )


class Showtime(Base):
    __tablename__ = "showtimes"
    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), index=True)
    auditorium_id: Mapped[int] = mapped_column(ForeignKey("auditoriums.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BDT")
    __table_args__ = (Index("ix_showtime_movie_start", "movie_id", "starts_at"),)

