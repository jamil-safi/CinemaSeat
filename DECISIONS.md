# Decisions

## Three services

We separated Browse, Booking, and Payment. This keeps catalog traffic independent from seat contention and isolates the unreliable gateway, at the cost of simple internal HTTP calls.

## Redis holds, PostgreSQL confirmations

Redis `SET NX EX` chooses one temporary hold winner quickly. PostgreSQL stores durable bookings and enforces one confirmed reservation per seat and showtime.

## Docker Compose on one VM

Compose and Nginx are enough for the required Poridhi deployment and clean-clone startup. Kubernetes or a message broker would add more operational work than this project needs.

