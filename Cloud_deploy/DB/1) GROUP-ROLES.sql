CREATE ROLE admin_group;
COMMENT ON ROLE admin_group IS 'Full rights over schema "report" (DDL + DML).';

CREATE ROLE writer_group;
COMMENT ON ROLE writer_group IS 'DML rights (SELECT/INSERT/UPDATE/DELETE) over schema "report".';

CREATE ROLE readonly_group;
COMMENT ON ROLE readonly_group IS 'Read-only access to schema "report".';

CREATE ROLE admin_user WITH LOGIN PASSWORD 'admin_password';
COMMENT ON ROLE admin_user IS 'Base admin';

CREATE ROLE writer_user WITH LOGIN PASSWORD 'writer_password';
COMMENT ON ROLE writer_user IS 'Base writer';

CREATE ROLE reader_user WITH LOGIN PASSWORD 'reader_password';
COMMENT ON ROLE reader_user IS 'Base reader';

GRANT admin_group    TO admin_user;
GRANT writer_group   TO writer_user;
GRANT readonly_group TO reader_user;