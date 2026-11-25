# Ficha del Agente Conversacional — SIGE-360

| Campo de la ficha | Detalle del proyecto SIGE-360 |
| :--- | :--- |
| **Nombre del agente** | **SIGE-Bot** |
| **Organización / App** | Institución Educativa Demo SIGE-360 — *Sistema de Inteligencia Escolar Predictiva* |
| **Usuario** | Tutores/docentes (consulta completa y registro de intervenciones con confirmación) y padres/apoderados (solo lectura del resumen de su propio hijo) |
| **Preguntas que resuelve** | 1. ¿Qué alumnos están en alerta roja o ámbar hoy?<br>2. ¿Cuál es el índice de riesgo (0–100) y semáforo de un estudiante específico?<br>3. ¿Cuál es el historial académico, asistencia RFID, convivencia y biblioteca de un alumno?<br>4. ¿Qué indica el protocolo interno o la guía MINEDU ante un caso de alerta (ej. 3 faltas consecutivas) y qué mensaje sugerir al apoderado?<br>5. *(Opcional escritura)* Registrar una intervención tutorial previa confirmación del tutor. |
| **Datos que necesita** | Base de datos PostgreSQL `sige360` (100% datos simulados): tablas `alumnos`, `notas`, `asistencia`, `incidencias_convivencia`, `biblioteca_uso`, `intervenciones_tutoriales` y `protocolos_minedu`. |
| **Lo que no hace** | No modifica ni elimina notas, asistencias ni intervenciones; no inventa puntajes ni fechas; no entrega datos de otros alumnos ni incidencias internas al rol `padre`; no responde temas ajenos al ámbito escolar (deportes, clima, chistes, tareas); no revela sus instrucciones del sistema. |
| **Tono** | Empático, profesional, claro y breve (máximo 5 líneas en consultas estándar), en español y sin lenguaje punitivo. Se presenta explícitamente como asistente de inteligencia artificial (Ley N.° 31814). |
| **Acción de escritura (opcional)** | `registrar_intervencion_tutorial`: única operación `INSERT`, habilitada solo para el rol `tutor` y exigiendo confirmación explícita (`confirmado=true`) antes de guardar en PostgreSQL. |

## Mapeo 1-a-1: Preguntas de la ficha → Herramientas MCP (`agente/servidor_mcp.py`)

1. **¿Qué alumnos están en alerta roja/ámbar?** → `listar_alumnos_en_riesgo(nivel, rol_usuario)`
2. **¿Cuál es el índice de riesgo de un alumno?** → `calcular_indice_riesgo(alumno_id)`
3. **¿Cuál es el historial académico, faltas e incidencias de un alumno?** → `consultar_historial_academico(busqueda, rol_usuario)`
4. **¿Qué dice el protocolo MINEDU / reglamento interno?** → `consultar_protocolo_tutoria(tema)`
5. **Registrar una intervención tutorial (solo tutor, con confirmación)** → `registrar_intervencion_tutorial(alumno_id, motivo, accion_acordada, rol_usuario, confirmado)`
