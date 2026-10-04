#!/bin/bash
# Создание БД FinDB с нужной локалью и владельцем admin_group.

set -e

echo "[init] Creating database FinDB..."

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" <<-'EOSQL'
    CREATE DATABASE "FinDB"
        OWNER = admin_group
        ENCODING = 'UTF8'
        LC_COLLATE = 'ru_RU.UTF-8'
        LC_CTYPE = 'ru_RU.UTF-8'
        TEMPLATE = template0
        CONNECTION LIMIT = 50;
EOSQL

echo "[init] Database FinDB created."