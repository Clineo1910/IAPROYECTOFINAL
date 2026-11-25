-- ============================================================================
-- Usuario de PostgreSQL con privilegios mínimos para el servidor MCP
-- Ejecutar en pgAdmin o psql conectado a la base de datos `sige360`
-- Cambia 'clave_sige360_segura' por la contraseña que pondrás en agente/.env
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'agente_sige') THEN
        CREATE ROLE agente_sige LOGIN PASSWORD 'clave_sige360_segura';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE sige360 TO agente_sige;
GRANT USAGE ON SCHEMA public TO agente_sige;

-- Lectura en todas las tablas de SIGE-360
GRANT SELECT ON ALL TABLES IN SCHEMA public TO agente_sige;

-- Única acción de escritura permitida (Paso 8.3 del instructivo):
-- registrar nuevas intervenciones tutoriales (sin UPDATE ni DELETE)
GRANT INSERT ON TABLE intervenciones_tutoriales TO agente_sige;
GRANT USAGE, SELECT ON SEQUENCE intervenciones_tutoriales_id_seq TO agente_sige;
