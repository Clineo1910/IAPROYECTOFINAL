# Reglas de Arquitectura y Seguridad — SIGE-360

- **Consultas SQL seguras:** usar siempre parámetros `%s` en `psycopg2` y cláusula `LIMIT`; nunca concatenar entrada del usuario ni usar `SELECT *`.
- **Privilegios mínimos:** el servidor MCP se conecta únicamente con el rol `agente_sige` (`SELECT` global + `INSERT` exclusivo en `intervenciones_tutoriales`, sin `UPDATE` ni `DELETE`).
- **Confirmación humana en escritura:** `registrar_intervencion_tutorial` exige `confirmado=True` únicamente después de que el tutor confirme el resumen.
- **Cero secretos en Git:** `.env` y credenciales de n8n permanecen locales y fuera del control de versiones.
- **Uso responsable de IA:** solo datos ficticios/simulados (Ley N.° 29733) y presentación transparente como asistente de IA (Ley N.° 31814).
