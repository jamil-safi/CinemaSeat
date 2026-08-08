from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .db import Base, SessionLocal, engine, get_session
from .models import Auditorium, Movie, Seat, Showtime, Theatre


async def seed() -> None:
    async with SessionLocal() as session:
        if await session.scalar(select(Movie.id).limit(1)):
            return
        session.add_all(
            [
                Movie(id=1, title="Brand New Day", duration_minutes=135),
                Movie(id=2, title="The Last Voyage", duration_minutes=118),
                Theatre(id=1, name="CinemaSeat Central", city="Chattogram"),
            ]
        )
        await session.flush()
        session.add(Auditorium(id=1, theatre_id=1, name="Hall 1"))
        await session.flush()
        session.add_all(
            Seat(id=index + 1, auditorium_id=1, row_label=row, number=number)
            for index, (row, number) in enumerate(
                (row, number) for row in ("A", "B", "C") for number in range(1, 11)
            )
        )
        tomorrow = datetime.now(UTC).replace(hour=20, minute=0, second=0, microsecond=0) + timedelta(days=1)
        session.add_all(
            [
                Showtime(id=1, movie_id=1, auditorium_id=1, starts_at=tomorrow, price=450, currency="BDT"),
                Showtime(id=2, movie_id=2, auditorium_id=1, starts_at=tomorrow + timedelta(hours=3), price=350, currency="BDT"),
            ]
        )
        await session.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await seed()
    yield
    await engine.dispose()


app = FastAPI(title="CinemaSeat Browse Service", lifespan=lifespan)


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/api/v1/movies")
async def movies(
    search: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = select(Movie).order_by(Movie.id).limit(limit).offset(offset)
    if search:
        query = query.where(Movie.title.ilike(f"%{search}%"))
    rows = (await session.scalars(query)).all()
    return [{"id": row.id, "title": row.title, "duration_minutes": row.duration_minutes} for row in rows]


@app.get("/api/v1/movies/{movie_id}")
async def movie(movie_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    row = await session.get(Movie, movie_id)
    if not row:
        raise HTTPException(404, "movie not found")
    return {"id": row.id, "title": row.title, "duration_minutes": row.duration_minutes}


@app.get("/api/v1/theatres")
async def theatres(
    city: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = select(Theatre).order_by(Theatre.id).limit(limit).offset(offset)
    if city:
        query = query.where(Theatre.city.ilike(city))
    rows = (await session.scalars(query)).all()
    return [{"id": row.id, "name": row.name, "city": row.city} for row in rows]


@app.get("/api/v1/showtimes")
async def showtimes(
    movie_id: int | None = None,
    theatre_id: int | None = None,
    show_date: date | None = Query(None, alias="date"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    query = select(Showtime, Auditorium).join(Auditorium).order_by(Showtime.starts_at).limit(limit).offset(offset)
    if movie_id:
        query = query.where(Showtime.movie_id == movie_id)
    if theatre_id:
        query = query.where(Auditorium.theatre_id == theatre_id)
    if show_date:
        start = datetime.combine(show_date, time.min, tzinfo=UTC)
        query = query.where(Showtime.starts_at >= start, Showtime.starts_at < start + timedelta(days=1))
    rows = (await session.execute(query)).all()
    return [
        {
            "id": show.id,
            "movie_id": show.movie_id,
            "theatre_id": auditorium.theatre_id,
            "auditorium_id": show.auditorium_id,
            "starts_at": show.starts_at,
            "price": float(show.price),
            "currency": show.currency,
        }
        for show, auditorium in rows
    ]


@app.get("/internal/v1/showtimes/{showtime_id}/seat-layout")
async def seat_layout(showtime_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    show = await session.get(Showtime, showtime_id)
    if not show:
        raise HTTPException(404, "showtime not found")
    auditorium = await session.get(Auditorium, show.auditorium_id)
    seats = (
        await session.scalars(
            select(Seat).where(Seat.auditorium_id == show.auditorium_id).order_by(Seat.id)
        )
    ).all()
    return {
        "showtime_id": show.id,
        "movie_id": show.movie_id,
        "auditorium_id": show.auditorium_id,
        "theatre_id": auditorium.theatre_id if auditorium else None,
        "starts_at": show.starts_at,
        "price": float(show.price),
        "currency": show.currency,
        "seats": [
            {"id": seat.id, "label": f"{seat.row_label}{seat.number}", "category": seat.category}
            for seat in seats
        ],
    }
