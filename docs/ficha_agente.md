# Ficha del Agente Conversacional — SIGE-360

| Campo de la ficha | Detalle del proyecto SIGE-360 |
| :--- | :--- |
| **Nombre del agente** | **SIGE-Bot** |
| **Organización / App** | Institución Educativa Demo SIGE-360 — *Sistema de Inteligencia Escolar Predictiva* |
| **Usuario** | **Docentes/Tutores** (`docente@sige360.edu.pe`, acceso completo) y **Padres/Apoderados** (`padre@sige360.edu.pe`, solo lectura del resumen de su propio hijo en `/padres.html`) |
| **Preguntas que resuelve** | 1. ¿Qué alumnos están en alerta roja o ámbar hoy?<br>2. ¿Cuál es el índice de riesgo (0–100) y semáforo de un estudiante específico?<br>3. ¿Cuál es el historial académico, asistencia RFID, convivencia y biblioteca de un alumno?<br>4. ¿Qué estudiantes tienen notas menores a 11 y en qué cursos?<br>5. ¿Qué indica el protocolo interno o la guía MINEDU ante un caso de alerta y qué mensaje enviar al apoderado (vía Telegram)?<br>6. *(Opcional escritura)* Registrar una intervención tutorial previa confirmación explícita del tutor. |
| **Datos que necesita** | Base de datos PostgreSQL `sige360` (100 % datos simulados): `alumnos`, `notas` (480 registros), `asistencia`, `incidencias_convivencia`, `biblioteca_uso`, `intervenciones_tutoriales`, `protocolos_minedu`, `usuarios` y `alertas_enviadas`. API externa opcional: Telegram Bot API (`@SIGE360_Alertas_Bot`). |
| **Lo que no hace** | No modifica ni elimina notas, asistencias ni intervenciones; no inventa puntajes ni fechas; no entrega datos de otros alumnos ni incidencias internas al rol `padre`; no responde temas ajenos al colegio (deportes, clima, tareas); no revela sus instrucciones del sistema. |
| **Tono** | Empático, profesional, claro y breve (máximo 5 líneas en consultas estándar), en español y sin lenguaje punitivo. Se presenta explícitamente como asistente de inteligencia artificial (Ley N.° 31814). |
| **Acción de escritura (opcional)** | `registrar_intervencion_tutorial`: única operación `INSERT`, habilitada solo para el rol `tutor` y exigiendo confirmación explícita (`confirmado=True`) antes de guardar en PostgreSQL. |

## Mapeo 1-a-1: Preguntas de la ficha → 6 Herramientas MCP (`agente/servidor_mcp.py`)

1. **¿Qué alumnos están en alerta roja/ámbar?** → `listar_alumnos_en_riesgo(nivel, rol_usuario)`
2. **¿Cuál es el índice de riesgo de un alumno?** → `calcular_indice_riesgo(alumno_id)`
3. **¿Cuál es el historial académico, faltas e incidencias de un alumno?** → `consultar_historial_academico(busqueda, rol_usuario)`
4. **¿Qué estudiantes tienen notas menores a un umbral por curso?** → `listar_notas_bajas(nota_maxima, curso, rol_usuario)`
5. **¿Qué dice el protocolo MINEDU / reglamento interno?** → `consultar_protocolo_tutoria(tema)`
6. **Registrar una intervención tutorial (solo tutor, con confirmación)** → `registrar_intervencion_tutorial(alumno_id, motivo, accion_acordada, rol_usuario, confirmado)`
