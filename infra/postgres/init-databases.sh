#!/bin/sh
set -eu

for database in browse_db booking_db payment_db; do
  if ! psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$database'" | grep -q 1; then
    createdb -U "$POSTGRES_USER" "$database"
  fi
done

