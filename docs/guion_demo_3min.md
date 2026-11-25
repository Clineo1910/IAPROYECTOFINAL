# Guion de Demostración en Vivo (3 Minutos) — SIGE-360

## 1. Contexto y problema (0:00 – 0:30 · 30 segundos)
- **Qué decir:** *"Somos el equipo de SIGE-360, un Sistema de Inteligencia Escolar Predictiva. En los colegios, las señales de deserción —faltas, bajas notas, convivencia y biblioteca— están dispersas. SIGE-360 cruza estas 4 señales desde PostgreSQL con 6 herramientas MCP y n8n para calcular un índice de riesgo (0–100), alertar en una pantalla semáforo de Sala de Profesores y notificar al apoderado por Telegram."*
- **Qué mostrar:** Login en `http://localhost:3060/login.html` → entrar como **Docente** (`docente@sige360.edu.pe` / `docente2026`) y tener abierta en otra pestaña la pantalla IoT `http://localhost:3060/semaforo.html`.

## 2. Tres preguntas en vivo + Factor Wow + Telegram (0:30 – 2:00 · 90 segundos)
1. **Pregunta 1 (Datos reales + Rayos X MCP):** Pulsar **"Alumnos en rojo"** o preguntar *"Lístame los estudiantes con notas menores a 11 y en qué cursos están así"* → señalar el panel **⚡ Rayos X MCP en Vivo** debajo del chat (o *Executions* en n8n) donde se ve la herramienta exacta ejecutada (`listar_notas_bajas` / `listar_alumnos_en_riesgo`) y el tiempo en milisegundos.
2. **Pregunta 2 (Factor Wow — Simulador RFID + Protocolo MINEDU + Telegram):** Pulsar **"Simular 3 faltas RFID + Nota 06"** sobre Lucas Mendoza (ID 3). Mostrar cómo la pantalla IoT `semaforo.html` cambia a **ROJO (82)** con banner de alerta, SIGE-Bot cita **PROT-04** y redacta el mensaje al apoderado → pulsar **"✈ Enviar por Telegram al apoderado"** y mostrar la notificación llegando en vivo al celular.
3. **Pregunta 3 (Seguridad por roles — Portal de Padres):** Cerrar sesión e ingresar como **Padre** (`padre@sige360.edu.pe` / `padre2026`) en `/padres.html`. Mostrar que solo ve las notas y asistencia de su hijo y pedir en el chat *"Dame la lista de todos los alumnos en alerta roja"* → SIGE-Bot bloquea el acceso citando **Ley N.° 29733**.

## 3. Pregunta fuera de alcance (2:00 – 2:30 · 30 segundos)
- Escribir en el chat: *"¿Quién ganó el partido de fútbol de ayer?"*
- Mostrar que SIGE-Bot reconoce sus límites, no inventa datos y se identifica como asistente de IA (**Ley N.° 31814**).

## 4. Qué aprendimos y qué mejoraríamos (2:30 – 3:00 · 30 segundos)
- **Aprendizajes:** Un agente real decide qué herramienta MCP usar sobre datos reales en PostgreSQL con usuario de privilegios mínimos (`agente_sige`), mantiene memoria por sesión, exige confirmación humana antes de escribir y protege la privacidad con datos 100 % simulados.
- **Mejoras futuras:** Conectar hardware físico ESP32/RC522 directo al endpoint `/api/rfid-scan`, agenda de citaciones con confirmación desde `/padres.html` y reportes históricos anuales.
