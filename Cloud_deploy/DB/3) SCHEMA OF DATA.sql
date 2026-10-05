\c "FinDB"

CREATE SCHEMA report AUTHORIZATION admin_group;

SET search_path TO report, public;

SET ROLE admin_group;

CREATE TABLE reasons (
	id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	name text NOT NULL UNIQUE

);

CREATE TABLE op_types (
	id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	name text NOT NULL UNIQUE
);

CREATE TABLE transactions (
	id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
	amount numeric(15, 2) NOT NULL,
	op_date date NOT NULL,
	reason_id int,
	type_id int,
	CONSTRAINT fk_transactions_reason 
		FOREIGN KEY (reason_id) REFERENCES reasons(id),
	CONSTRAINT fk_transactions_op_type 
		FOREIGN KEY (type_id) REFERENCES op_types(id)
);

RESET ROLE;