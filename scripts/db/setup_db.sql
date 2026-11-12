-- =====================================================================
-- Plataforma Hídrica Zulia — creación de la base de datos local
-- PostgreSQL 18 + PostGIS
--
-- No lo ejecutes directamente: usa scripts\db\setup_db.ps1, que pasa la
-- contraseña de la aplicación (DB_PASSWORD del .env) como variable
-- :app_password y pide la contraseña de "postgres" de forma interactiva.
--
-- Se puede ejecutar varias veces sin error.
-- =====================================================================
\set ON_ERROR_STOP on

-- 1) Usuario de la aplicación (no es superusuario)
SELECT format('CREATE ROLE hidrica_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hidrica_app')
\gexec
SELECT format('ALTER ROLE hidrica_app LOGIN PASSWORD %L', :'app_password')
\gexec

-- 2) Bases de datos: principal y de pruebas
SELECT 'CREATE DATABASE plataforma_hidrica OWNER hidrica_app ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'plataforma_hidrica')
\gexec
SELECT 'CREATE DATABASE plataforma_hidrica_test OWNER hidrica_app ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'plataforma_hidrica_test')
\gexec

-- 3) PostGIS en cada base (requiere superusuario)
\connect plataforma_hidrica
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT 'plataforma_hidrica' AS base, postgis_full_version() AS postgis;

\connect plataforma_hidrica_test
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT 'plataforma_hidrica_test' AS base, postgis_lib_version() AS postgis;
