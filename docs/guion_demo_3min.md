# Guion de Demostración en Vivo (3 Minutos) — SIGE-360

> **Antes de empezar:** Tener corriendo los 3 servicios (`Ctrl + Shift + B` o `iniciar_sige360.bat`): **Servidor MCP (:8000)**, **n8n (:5678)** y **App Web FastAPI (:3060)**. Tener listas 2 pestañas: `/login.html` y `/semaforo.html`, más Telegram abierto en el celular (`@SIGE360_Alertas_Bot`).

---

## 1. Contexto y problema (0:00 – 0:25 · 25 segundos)
- **Qué decir:** *"Somos el equipo de SIGE-360, un Sistema de Inteligencia Escolar Predictiva para colegios de secundaria. Hoy las señales de deserción —asistencia, notas, convivencia y biblioteca— están aisladas. SIGE-360 las integra en PostgreSQL y conecta un agente conversacional en n8n + Gemini con 6 herramientas MCP para calcular un índice de riesgo (0–100), alertar en un semáforo IoT de Sala de Profesores y comunicarse con los padres en vivo por Telegram."*
- **Qué mostrar:** Ingresar en `http://localhost:3060/login.html` como **Docente** (`docente@sige360.edu.pe` / `docente2026`) y mostrar brevemente el Dashboard Ejecutivo y el Registro de Notas matricial de 4 bimestres (`/notas.html`).

---

## 2. Datos reales en vivo + Doble comprobación MCP (0:25 – 1:00 · 35 segundos)
- **Qué hacer:** En el chat de **SIGE-Bot**, pulsar **"Alumnos en rojo"** o preguntar: *"¿Qué estudiantes tienen notas menores a 11 y en qué cursos?"*.
- **Qué señalar:** Mostrar la consola del **Servidor MCP (:8000)** (o el panel **⚡ Rayos X MCP**), donde aparece en tiempo real `[MCP] listar_notas_bajas(...)` y `[MCP -> RESULTADO]` con los datos exactos traídos desde PostgreSQL y el tiempo en milisegundos.
- **Bonus rápido (5 s):** Abrir una **Ficha 360°** y señalar el botón **"🖨️ Exportar PDF"** para reportes formales de tutoría.

---

## 3. Factor Wow: Simulador RFID + Pantalla IoT + Bot Interactivo Telegram (1:00 – 1:55 · 55 segundos)
1. Pulsar **"Simular 3 faltas RFID + Nota 06"** sobre **Lucas Mendoza Paredes (ID 3)**.
2. Cambiar 5 segundos a la pestaña IoT `http://localhost:3060/semaforo.html` para mostrar cómo Lucas saltó a **ALERTA ROJA** con banner en tiempo real.
3. En SIGE-Bot, mostrar que el agente citó el protocolo **PROT-04 (MINEDU)** desde RAG y redactó el mensaje empático al apoderado → pulsar **"✈ Enviar por Telegram al apoderado"**.
4. **Momento estelar en el celular:** Mostrar la alerta llegando en vivo a `@SIGE360_Alertas_Bot` con botones interactivos → tocar **`📊 Ver historial y notas`** (o responder *"sí"*). Señalar en la consola cómo la consulta desde Telegram **también pasa 100% por `n8n → Gemini → Servidor MCP → PostgreSQL`** y responde ordenada en secciones con las notas reales del estudiante.

---

## 4. Seguridad por roles, Privacidad y Fuera de Alcance (1:55 – 2:35 · 40 segundos)
1. Cerrar sesión e ingresar como **Padre** (`padre@sige360.edu.pe` / `padre2026`) en `/padres.html`.
2. Mostrar la **Boleta de Calificaciones matricial (6 cursos × 4 bimestres)** y el botón **"🖨️ Exportar Boleta PDF"**.
3. Probar dos controles clave en el chat familiar:
   - **Privacidad (Ley N.° 29733):** *"Dame la lista de todos los alumnos en alerta roja"* → SIGE-Bot bloquea el acceso (solo datos de su propio hijo).
   - **Fuera de alcance (Ley N.° 31814):** *"¿Quién ganó el partido de fútbol de ayer?"* → SIGE-Bot reconoce sus límites, no inventa datos y se identifica como asistente de IA.

---

## 5. Qué aprendimos y qué mejoraríamos (2:35 – 3:00 · 25 segundos)
- **Aprendizajes:** Un agente real no improvisa respuestas: decide qué herramienta MCP ejecutar sobre PostgreSQL con usuario de mínimo privilegio (`agente_sige`), exige confirmación humana antes de escribir (`registrar_intervencion_tutorial`), protege sesiones con `scrypt` + RBAC y opera con datos 100 % simulados.
- **Mejoras futuras:** Conectar hardware físico ESP32/RC522 directo al endpoint `/api/rfid-scan`, sumar canal WhatsApp Business Cloud API en n8n y reportes predictivos comparativos entre años escolares.

*(Al terminar la demo, pulsar **"Reiniciar demo"** en el Dashboard para devolver a Lucas Mendoza a su estado base ÁMBAR).*
