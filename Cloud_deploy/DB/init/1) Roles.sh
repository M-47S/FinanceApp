#!/bin/bash
# Создание групп и пользователей с паролями из ENV.
# Пароли НЕ хранятся в файле — приходят через переменные окружения контейнера.

set -e

# Проверка, что нужные переменные заданы
: "${ADMIN_USER_PASSWORD:?ADMIN_USER_PASSWORD is not set}"
: "${WRITER_USER_PASSWORD:?WRITER_USER_PASSWORD is not set}"
: "${READER_USER_PASSWORD:?READER_USER_PASSWORD is not set}"

echo "[init] Creating roles and users..."

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     -v admin_pwd="$ADMIN_USER_PASSWORD" \
     -v writer_pwd="$WRITER_USER_PASSWORD" \
     -v reader_pwd="$READER_USER_PASSWORD" <<-'EOSQL'
    -- Группы (NOLOGIN по умолчанию)
    CREATE ROLE admin_group;
    COMMENT ON ROLE admin_group IS 'Full rights over schema "report" (DDL + DML).';

    CREATE ROLE writer_group;
    COMMENT ON ROLE writer_group IS 'DML rights (SELECT/INSERT/UPDATE/DELETE) over schema "report".';

    CREATE ROLE readonly_group;
    COMMENT ON ROLE readonly_group IS 'Read-only access to schema "report".';

    -- Пользователи
    CREATE ROLE admin_user  WITH LOGIN PASSWORD :'admin_pwd';
    COMMENT ON ROLE admin_user IS 'Base admin';

    CREATE ROLE writer_user WITH LOGIN PASSWORD :'writer_pwd';
    COMMENT ON ROLE writer_user IS 'Base writer';

    CREATE ROLE reader_user WITH LOGIN PASSWORD :'reader_pwd';
    COMMENT ON ROLE reader_user IS 'Base reader';

    -- Членство
    GRANT admin_group    TO admin_user;
    GRANT writer_group   TO writer_user;
    GRANT readonly_group TO reader_user;
EOSQL

echo "[init] Roles and users created."