# Guion de Demostración en Vivo (3 Minutos) — SIGE-360

## 1. Contexto y problema (0:00 – 0:30 · 30 segundos)
- **Qué decir:** *"Somos el equipo de SIGE-360, un Sistema de Inteligencia Escolar Predictiva. En muchos colegios las señales de deserción —faltas, bajas notas, incidencias de convivencia y desvinculación en biblioteca— están dispersas y se detectan demasiado tarde. Nuestro agente SIGE-Bot cruza estas 4 señales desde PostgreSQL vía MCP y n8n para calcular un índice de riesgo (0 a 100) y guiar al tutor según los protocolos del MINEDU."*
- **Qué mostrar:** Dashboard principal en `http://localhost:3060` y, en paralelo (o tablet), la pantalla IoT `http://localhost:3060/semaforo.html`.

## 2. Tres preguntas en vivo + Factor Wow (0:30 – 2:00 · 90 segundos)
1. **Pregunta 1 (Listado de riesgo):** Escribir en el chat *"¿Qué alumnos están en alerta roja hoy?"* → Muestra a Mateo Quispe (100), Diego Huamán (85) y Thiago Chávez (72). **Mostrar rápidamente la pestaña de ejecuciones de n8n** donde se ve que el AI Agent llamó a la herramienta MCP `listar_alumnos_en_riesgo`.
2. **Pregunta 2 (Factor Wow — Simulador RFID + Protocolo MINEDU):** Pulsar **"Simular 3 faltas RFID + Nota 06"** sobre Lucas Mendoza (ID 3). Mostrar cómo el semáforo de la pantalla IoT cambia en vivo de **ÁMBAR (35)** a **ROJO (82)** y SIGE-Bot consulta `calcular_indice_riesgo` + `consultar_protocolo_tutoria` para citar **PROT-04** y redactar el mensaje empático al apoderado.
3. **Pregunta 3 (Permisos por rol):** Cambiar el botón superior a **Padre / Apoderado** y pedir *"Dame la lista de todos los alumnos en riesgo"* → SIGE-Bot rechaza la solicitud citando confidencialidad (PROT-10 / Ley N.° 29733).

## 3. Pregunta fuera de alcance (2:00 – 2:30 · 30 segundos)
- Escribir: *"¿Quién ganó el partido de fútbol de ayer?"*
- Mostrar que SIGE-Bot reconoce sus límites, no inventa datos y recuerda en qué sí puede ayudar.

## 4. Qué aprendimos y qué mejoraríamos (2:30 – 3:00 · 30 segundos)
- **Aprendizajes:** Un agente real no improvisa; decide qué herramienta MCP ejecutar sobre datos reales en PostgreSQL, mantiene memoria por sesión y respeta permisos y privacidad (solo datos simulados, Ley N.° 29733 y transparencia Ley N.° 31814).
- **Mejoras futuras:** Conectar un lector RFID físico ESP32/RC522 directo a `/api/simular-rfid`, añadir notificaciones WhatsApp/correo aprobadas por el tutor y paneles históricos por bimestre.
