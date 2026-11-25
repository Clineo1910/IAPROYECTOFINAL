-- ============================================================================
-- SIGE-360: Sistema de Inteligencia Escolar Predictiva
-- Base de datos PostgreSQL (UTF-8) con datos 100% SIMULADOS
-- Nota: Ningún nombre, código ni contacto corresponde a personas reales
--       (cumplimiento Ley N.° 29733 de Protección de Datos Personales).
-- ============================================================================
-- Ejecuta primero (si aún no existe la BD):
--   CREATE DATABASE sige360 WITH ENCODING 'UTF8';
-- Luego conéctate a la BD `sige360` y ejecuta este script completo.

DROP TABLE IF EXISTS intervenciones_tutoriales CASCADE;
DROP TABLE IF EXISTS biblioteca_uso CASCADE;
DROP TABLE IF EXISTS incidencias_convivencia CASCADE;
DROP TABLE IF EXISTS asistencia CASCADE;
DROP TABLE IF EXISTS notas CASCADE;
DROP TABLE IF EXISTS protocolos_minedu CASCADE;
DROP TABLE IF EXISTS alumnos CASCADE;

-- 1. Tabla de alumnos (20 registros simulados)
CREATE TABLE alumnos (
    id SERIAL PRIMARY KEY,
    codigo_estudiante VARCHAR(12) NOT NULL UNIQUE,
    codigo_rfid VARCHAR(20) NOT NULL UNIQUE,
    nombre_completo VARCHAR(100) NOT NULL,
    grado VARCHAR(20) NOT NULL,
    seccion CHAR(1) NOT NULL,
    apoderado_nombre VARCHAR(100) NOT NULL,
    apoderado_contacto VARCHAR(100) NOT NULL
);

-- 2. Tabla de notas (escala vigesimal 0-20)
CREATE TABLE notas (
    id SERIAL PRIMARY KEY,
    alumno_id INT NOT NULL REFERENCES alumnos(id) ON DELETE RESTRICT,
    curso VARCHAR(60) NOT NULL,
    bimestre SMALLINT NOT NULL,
    nota NUMERIC(4,2) NOT NULL,
    fecha_registro DATE NOT NULL
);

-- 3. Tabla de asistencia (registrada por lector RFID en puerta o manual)
CREATE TABLE asistencia (
    id SERIAL PRIMARY KEY,
    alumno_id INT NOT NULL REFERENCES alumnos(id) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    estado VARCHAR(12) NOT NULL CHECK (estado IN ('PRESENTE', 'TARDANZA', 'FALTA')),
    hora_rfid TIME NULL,
    origen VARCHAR(15) NOT NULL DEFAULT 'RFID_PUERTA' CHECK (origen IN ('RFID_PUERTA', 'MANUAL'))
);

-- 4. Tabla de incidencias de convivencia escolar
CREATE TABLE incidencias_convivencia (
    id SERIAL PRIMARY KEY,
    alumno_id INT NOT NULL REFERENCES alumnos(id) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('DISRUPCION', 'CONFLICTO', 'AISLAMIENTO', 'RECONOCIMIENTO')),
    gravedad VARCHAR(10) NOT NULL CHECK (gravedad IN ('BAJA', 'MEDIA', 'ALTA')),
    descripcion VARCHAR(255) NOT NULL
);

-- 5. Tabla de comportamiento en biblioteca
CREATE TABLE biblioteca_uso (
    id SERIAL PRIMARY KEY,
    alumno_id INT NOT NULL REFERENCES alumnos(id) ON DELETE RESTRICT,
    fecha DATE NOT NULL,
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('PRESTAMO', 'LECTURA_SALA', 'DEVOLUCION_TARDIA', 'NO_DEVUELTO')),
    libro VARCHAR(120) NOT NULL
);

-- 6. Tabla de intervenciones tutoriales (única tabla con permiso de escritura para el agente)
CREATE TABLE intervenciones_tutoriales (
    id SERIAL PRIMARY KEY,
    alumno_id INT NOT NULL REFERENCES alumnos(id) ON DELETE RESTRICT,
    fecha TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    tutor_nombre VARCHAR(100) NOT NULL DEFAULT 'Tutor SIGE-360',
    motivo VARCHAR(255) NOT NULL,
    accion_acordada VARCHAR(255) NOT NULL,
    estado VARCHAR(15) NOT NULL DEFAULT 'PROGRAMADA' CHECK (estado IN ('PROGRAMADA', 'REALIZADA', 'SEGUIMIENTO'))
);

-- 7. Tabla de protocolos internos y guías MINEDU (base de conocimiento RAG)
CREATE TABLE protocolos_minedu (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(20) NOT NULL UNIQUE,
    categoria VARCHAR(50) NOT NULL,
    titulo VARCHAR(140) NOT NULL,
    nivel_riesgo VARCHAR(10) NOT NULL CHECK (nivel_riesgo IN ('VERDE', 'AMBAR', 'ROJO', 'GENERAL')),
    contenido TEXT NOT NULL
);

-- ============================================================================
-- INSERCIÓN DE DATOS SIMULADOS (20 ALUMNOS)
-- ============================================================================
INSERT INTO alumnos (id, codigo_estudiante, codigo_rfid, nombre_completo, grado, seccion, apoderado_nombre, apoderado_contacto) VALUES
(1,  'EST-2026-001', 'RFID-A101', 'Mateo Quispe Ramos',       '3ro Secundaria', 'A', 'Carmen Ramos (Demo)',      'apoderado01@demo.sige360.local'),
(2,  'EST-2026-002', 'RFID-A102', 'Valeria Torres Luna',      '3ro Secundaria', 'A', 'Jorge Torres (Demo)',      'apoderado02@demo.sige360.local'),
(3,  'EST-2026-003', 'RFID-A103', 'Lucas Mendoza Paredes',    '4to Secundaria', 'B', 'Elena Paredes (Demo)',     'apoderado03@demo.sige360.local'),
(4,  'EST-2026-004', 'RFID-A104', 'Sofía Vargas Castillo',    '4to Secundaria', 'B', 'Raúl Vargas (Demo)',       'apoderado04@demo.sige360.local'),
(5,  'EST-2026-005', 'RFID-A105', 'Diego Huamán Flores',      '5to Secundaria', 'A', 'Rosa Flores (Demo)',       'apoderado05@demo.sige360.local'),
(6,  'EST-2026-006', 'RFID-A106', 'Camila Rojas Díaz',        '2do Secundaria', 'C', 'Luis Rojas (Demo)',        'apoderado06@demo.sige360.local'),
(7,  'EST-2026-007', 'RFID-A107', 'Sebastián Cruz Vega',      '3ro Secundaria', 'B', 'Patricia Vega (Demo)',     'apoderado07@demo.sige360.local'),
(8,  'EST-2026-008', 'RFID-A108', 'Luciana Morales Silva',    '1ro Secundaria', 'A', 'Carlos Morales (Demo)',    'apoderado08@demo.sige360.local'),
(9,  'EST-2026-009', 'RFID-A109', 'Thiago Chávez Ortiz',      '5to Secundaria', 'B', 'Marta Ortiz (Demo)',       'apoderado09@demo.sige360.local'),
(10, 'EST-2026-010', 'RFID-A110', 'Antonella Paredes Cruz',   '2do Secundaria', 'A', 'Héctor Paredes (Demo)',    'apoderado10@demo.sige360.local'),
(11, 'EST-2026-011', 'RFID-A111', 'Gabriel Salazar Peña',     '4to Secundaria', 'A', 'Silvia Peña (Demo)',       'apoderado11@demo.sige360.local'),
(12, 'EST-2026-012', 'RFID-A112', 'Renata Aguilar Ríos',      '1ro Secundaria', 'B', 'Oscar Aguilar (Demo)',     'apoderado12@demo.sige360.local'),
(13, 'EST-2026-013', 'RFID-A113', 'Bruno Medina Castro',      '3ro Secundaria', 'C', 'Nadia Castro (Demo)',      'apoderado13@demo.sige360.local'),
(14, 'EST-2026-014', 'RFID-A114', 'Isabella Navarro León',    '5to Secundaria', 'A', 'Miguel Navarro (Demo)',    'apoderado14@demo.sige360.local'),
(15, 'EST-2026-015', 'RFID-A115', 'Adrián Herrera Soto',      '2do Secundaria', 'B', 'Lucía Soto (Demo)',        'apoderado15@demo.sige360.local'),
(16, 'EST-2026-016', 'RFID-A116', 'Mía Delgado Campos',       '4to Secundaria', 'C', 'Fernando Delgado (Demo)',  'apoderado16@demo.sige360.local'),
(17, 'EST-2026-017', 'RFID-A117', 'Joaquín Cárdenas Ruiz',    '1ro Secundaria', 'A', 'Beatriz Ruiz (Demo)',      'apoderado17@demo.sige360.local'),
(18, 'EST-2026-018', 'RFID-A118', 'Valentina Espinoza Paz',   '3ro Secundaria', 'A', 'Daniel Espinoza (Demo)',   'apoderado18@demo.sige360.local'),
(19, 'EST-2026-019', 'RFID-A119', 'Nicolás Cabrera Mejía',    '5to Secundaria', 'B', 'Gloria Mejía (Demo)',      'apoderado19@demo.sige360.local'),
(20, 'EST-2026-020', 'RFID-A120', 'Paula Guzmán Herrera',     '2do Secundaria', 'C', 'Andrés Guzmán (Demo)',     'apoderado20@demo.sige360.local');

SELECT setval(pg_get_serial_sequence('alumnos', 'id'), (SELECT MAX(id) FROM alumnos));

-- ============================================================================
-- NOTAS (40 registros simulados)
-- ============================================================================
INSERT INTO notas (alumno_id, curso, bimestre, nota, fecha_registro) VALUES
(1,  'Matemática',    3,  8.00, '2026-11-10'),
(1,  'Comunicación',  3, 10.00, '2026-11-12'),
(2,  'Matemática',    3, 17.00, '2026-11-10'),
(2,  'Comunicación',  3, 18.00, '2026-11-12'),
(3,  'Matemática',    3, 12.00, '2026-11-10'),
(3,  'Comunicación',  3, 14.00, '2026-11-12'),
(4,  'Matemática',    3, 16.00, '2026-11-10'),
(4,  'Comunicación',  3, 15.00, '2026-11-12'),
(5,  'Matemática',    3,  9.00, '2026-11-10'),
(5,  'Comunicación',  3, 10.00, '2026-11-12'),
(6,  'Matemática',    3, 15.00, '2026-11-10'),
(6,  'Comunicación',  3, 16.00, '2026-11-12'),
(7,  'Matemática',    3, 11.00, '2026-11-10'),
(7,  'Comunicación',  3, 12.00, '2026-11-12'),
(8,  'Matemática',    3, 18.00, '2026-11-10'),
(8,  'Comunicación',  3, 17.00, '2026-11-12'),
(9,  'Matemática',    3,  9.00, '2026-11-10'),
(9,  'Comunicación',  3, 11.00, '2026-11-12'),
(10, 'Matemática',    3, 16.00, '2026-11-10'),
(10, 'Comunicación',  3, 17.00, '2026-11-12'),
(11, 'Matemática',    3, 11.00, '2026-11-10'),
(11, 'Comunicación',  3, 13.00, '2026-11-12'),
(12, 'Matemática',    3, 15.00, '2026-11-10'),
(12, 'Comunicación',  3, 16.00, '2026-11-12'),
(13, 'Matemática',    3, 14.00, '2026-11-10'),
(13, 'Comunicación',  3, 15.00, '2026-11-12'),
(14, 'Matemática',    3, 19.00, '2026-11-10'),
(14, 'Comunicación',  3, 18.00, '2026-11-12'),
(15, 'Matemática',    3, 11.00, '2026-11-10'),
(15, 'Comunicación',  3, 12.00, '2026-11-12'),
(16, 'Matemática',    3, 16.00, '2026-11-10'),
(16, 'Comunicación',  3, 15.00, '2026-11-12'),
(17, 'Matemática',    3, 17.00, '2026-11-10'),
(17, 'Comunicación',  3, 16.00, '2026-11-12'),
(18, 'Matemática',    3, 15.00, '2026-11-10'),
(18, 'Comunicación',  3, 16.00, '2026-11-12'),
(19, 'Matemática',    3, 14.00, '2026-11-10'),
(19, 'Comunicación',  3, 15.00, '2026-11-12'),
(20, 'Matemática',    3, 18.00, '2026-11-10'),
(20, 'Comunicación',  3, 17.00, '2026-11-12');

-- ============================================================================
-- ASISTENCIA (34 registros simulados recientes - noviembre 2026)
-- ============================================================================
INSERT INTO asistencia (alumno_id, fecha, estado, hora_rfid, origen) VALUES
-- Mateo Quispe (ID 1): 4 faltas -> ROJO crítico
(1, '2026-11-16', 'FALTA',    NULL,       'RFID_PUERTA'),
(1, '2026-11-17', 'FALTA',    NULL,       'RFID_PUERTA'),
(1, '2026-11-18', 'FALTA',    NULL,       'RFID_PUERTA'),
(1, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Valeria Torres (ID 2): presente -> VERDE
(2, '2026-11-18', 'PRESENTE', '07:45:00', 'RFID_PUERTA'),
(2, '2026-11-19', 'PRESENTE', '07:42:00', 'RFID_PUERTA'),
-- Lucas Mendoza (ID 3): 1 falta + 1 tardanza -> ÁMBAR (listo para Factor Wow RFID)
(3, '2026-11-18', 'TARDANZA', '08:15:00', 'RFID_PUERTA'),
(3, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Sofía Vargas (ID 4): presente -> VERDE
(4, '2026-11-18', 'PRESENTE', '07:50:00', 'RFID_PUERTA'),
(4, '2026-11-19', 'PRESENTE', '07:48:00', 'RFID_PUERTA'),
-- Diego Huamán (ID 5): 3 faltas + 1 tardanza -> ROJO crítico
(5, '2026-11-16', 'TARDANZA', '08:20:00', 'RFID_PUERTA'),
(5, '2026-11-17', 'FALTA',    NULL,       'RFID_PUERTA'),
(5, '2026-11-18', 'FALTA',    NULL,       'RFID_PUERTA'),
(5, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Camila Rojas (ID 6)
(6, '2026-11-19', 'PRESENTE', '07:40:00', 'RFID_PUERTA'),
-- Sebastián Cruz (ID 7): 2 faltas -> ÁMBAR
(7, '2026-11-18', 'FALTA',    NULL,       'RFID_PUERTA'),
(7, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Luciana Morales (ID 8)
(8, '2026-11-19', 'PRESENTE', '07:38:00', 'RFID_PUERTA'),
-- Thiago Chávez (ID 9): 3 faltas -> ROJO
(9, '2026-11-17', 'FALTA',    NULL,       'RFID_PUERTA'),
(9, '2026-11-18', 'FALTA',    NULL,       'RFID_PUERTA'),
(9, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Antonella Paredes (ID 10)
(10, '2026-11-19', 'PRESENTE', '07:44:00', 'RFID_PUERTA'),
-- Gabriel Salazar (ID 11): 2 faltas -> ÁMBAR
(11, '2026-11-18', 'FALTA',    NULL,       'RFID_PUERTA'),
(11, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Renata Aguilar (ID 12)
(12, '2026-11-19', 'PRESENTE', '07:46:00', 'RFID_PUERTA'),
-- Bruno Medina (ID 13)
(13, '2026-11-19', 'PRESENTE', '07:51:00', 'RFID_PUERTA'),
-- Isabella Navarro (ID 14)
(14, '2026-11-19', 'PRESENTE', '07:35:00', 'RFID_PUERTA'),
-- Adrián Herrera (ID 15): 1 falta + 1 tardanza -> ÁMBAR
(15, '2026-11-18', 'TARDANZA', '08:12:00', 'RFID_PUERTA'),
(15, '2026-11-19', 'FALTA',    NULL,       'RFID_PUERTA'),
-- Resto presentes -> VERDE
(16, '2026-11-19', 'PRESENTE', '07:47:00', 'RFID_PUERTA'),
(17, '2026-11-19', 'PRESENTE', '07:49:00', 'RFID_PUERTA'),
(18, '2026-11-19', 'PRESENTE', '07:41:00', 'RFID_PUERTA'),
(19, '2026-11-19', 'PRESENTE', '07:53:00', 'RFID_PUERTA'),
(20, '2026-11-19', 'PRESENTE', '07:39:00', 'RFID_PUERTA');

-- ============================================================================
-- INCIDENCIAS DE CONVIVENCIA (16 registros simulados)
-- ============================================================================
INSERT INTO incidencias_convivencia (alumno_id, fecha, tipo, gravedad, descripcion) VALUES
(1,  '2026-11-05', 'AISLAMIENTO',    'ALTA',  'Se aísla en recreos y manifiesta desmotivación por continuar el año.'),
(1,  '2026-11-14', 'CONFLICTO',      'ALTA',  'Discusión reiterada en aula durante clase de Matemática.'),
(2,  '2026-11-10', 'RECONOCIMIENTO', 'BAJA',  'Apoyó voluntariamente en el taller de lectura.'),
(3,  '2026-11-15', 'DISRUPCION',     'MEDIA', 'Distracción constante y salida del aula sin permiso.'),
(5,  '2026-11-12', 'AISLAMIENTO',    'ALTA',  'Reporta sobrecarga familiar y fatiga constante en clase.'),
(7,  '2026-11-11', 'DISRUPCION',     'MEDIA', 'Incumplimiento reiterado de acuerdos de convivencia.'),
(8,  '2026-11-09', 'RECONOCIMIENTO', 'BAJA',  'Delegada de aula destacada por mediación escolar.'),
(9,  '2026-11-13', 'CONFLICTO',      'MEDIA', 'Incidente verbal con compañero en laboratorio.'),
(11, '2026-11-14', 'DISRUPCION',     'BAJA',  'Uso de celular durante evaluación formativa.'),
(14, '2026-11-08', 'RECONOCIMIENTO', 'BAJA',  'Primer puesto en olimpiada interna de ciencias.'),
(15, '2026-11-16', 'AISLAMIENTO',    'MEDIA', 'Baja participación grupal en las últimas dos semanas.'),
(16, '2026-11-11', 'RECONOCIMIENTO', 'BAJA',  'Colaboración destacada en feria ambiental.'),
(17, '2026-11-12', 'RECONOCIMIENTO', 'BAJA',  'Asistencia puntual todo el bimestre.'),
(18, '2026-11-13', 'DISRUPCION',     'BAJA',  'Conversación reiterada durante exposición.'),
(19, '2026-11-15', 'RECONOCIMIENTO', 'BAJA',  'Tutor par en curso de Matemática.'),
(20, '2026-11-16', 'RECONOCIMIENTO', 'BAJA',  'Líder de club de lectura escolar.');

-- ============================================================================
-- COMPORTAMIENTO EN BIBLIOTECA (16 registros simulados)
-- ============================================================================
INSERT INTO biblioteca_uso (alumno_id, fecha, accion, libro) VALUES
(1,  '2026-10-28', 'NO_DEVUELTO',       'Álgebra Básica 3'),
(2,  '2026-11-12', 'LECTURA_SALA',      'Cuentos Andinos'),
(3,  '2026-11-09', 'DEVOLUCION_TARDIA', 'Historia del Perú Contemporáneo'),
(4,  '2026-11-14', 'PRESTAMO',          'Física Conceptual'),
(5,  '2026-11-02', 'NO_DEVUELTO',       'Razonamiento Matemático 5'),
(6,  '2026-11-15', 'LECTURA_SALA',      'Antología Poética'),
(7,  '2026-11-07', 'DEVOLUCION_TARDIA', 'Química General'),
(8,  '2026-11-18', 'PRESTAMO',          'El Principito'),
(9,  '2026-11-04', 'DEVOLUCION_TARDIA', 'Geometría Analítica'),
(10, '2026-11-17', 'LECTURA_SALA',      'Biología Moderna'),
(11, '2026-11-06', 'DEVOLUCION_TARDIA', 'Literatura Peruana'),
(12, '2026-11-16', 'PRESTAMO',          'Aventuras de la Ciencia'),
(14, '2026-11-19', 'LECTURA_SALA',      'Cálculo Introductorio'),
(15, '2026-11-08', 'DEVOLUCION_TARDIA', 'Comunicación Integral 2'),
(17, '2026-11-15', 'PRESTAMO',          'Atlas Geográfico'),
(20, '2026-11-18', 'LECTURA_SALA',      'Mitos y Leyendas del Perú');

-- ============================================================================
-- INTERVENCIONES TUTORIALES (15 registros simulados)
-- ============================================================================
INSERT INTO intervenciones_tutoriales (alumno_id, tutor_nombre, motivo, accion_acordada, estado) VALUES
(1,  'Prof. Ana Salas',   'Inasistencias acumuladas en noviembre',           'Entrevista inicial con estudiante y derivación a psicología', 'SEGUIMIENTO'),
(1,  'Prof. Ana Salas',   'Bajo rendimiento en Matemática (08)',             'Plan de refuerzo martes y jueves',                            'PROGRAMADA'),
(3,  'Prof. Carlos Díaz', 'Tardanzas y distracción en aula',                 'Acuerdo de puntualidad y seguimiento quincenal',              'REALIZADA'),
(5,  'Prof. Ana Salas',   'Tres faltas consecutivas y fatiga escolar',       'Citación urgente a apoderado y evaluación de horario',        'SEGUIMIENTO'),
(7,  'Prof. Carlos Díaz', 'Baja en promedio de Matemática y 2 faltas',       'Sesión de hábitos de estudio',                                'PROGRAMADA'),
(9,  'Prof. Ana Salas',   'Conflicto verbal y ausentismo reciente',          'Mediación escolar y llamada preventiva al apoderado',         'SEGUIMIENTO'),
(11, 'Prof. Carlos Díaz', 'Dos faltas consecutivas sin justificación',       'Verificación telefónica con familia',                         'REALIZADA'),
(15, 'Prof. Ana Salas',   'Aislamiento progresivo en clase',                 'Observación socioemocional en tutoría grupal',                'SEGUIMIENTO'),
(2,  'Prof. Carlos Díaz', 'Seguimiento preventivo de excelencia',            'Invitación a programa de tutoría entre pares',                'REALIZADA'),
(4,  'Prof. Carlos Díaz', 'Orientación vocacional trimestral',               'Aplicación de test de intereses',                             'REALIZADA'),
(6,  'Prof. Ana Salas',   'Seguimiento de adaptación escolar',               'Sin observaciones de riesgo',                                 'REALIZADA'),
(10, 'Prof. Ana Salas',   'Revisión de metas académicas',                    'Refuerzo positivo en lectura',                                'REALIZADA'),
(13, 'Prof. Carlos Díaz', 'Consulta por organización de horarios',           'Entrega de cronograma de estudio',                            'REALIZADA'),
(18, 'Prof. Ana Salas',   'Recordatorio de normas de aula',                  'Compromiso verbal cumplido',                                  'REALIZADA'),
(19, 'Prof. Carlos Díaz', 'Seguimiento vocacional 5to secundaria',           'Charla sobre becas universitarias',                           'REALIZADA');

-- ============================================================================
-- PROTOCOLOS INTERNOS Y GUÍAS MINEDU (15 registros para RAG vía MCP)
-- ============================================================================
INSERT INTO protocolos_minedu (codigo, categoria, titulo, nivel_riesgo, contenido) VALUES
('PROT-01', 'ALERTA_TEMPRANA', 'Umbral de Alerta Roja por Deserción (MINEDU)', 'ROJO',
 'Todo estudiante con índice de riesgo >= 60, o con 3 o más faltas consecutivas injustificadas combinadas con promedio desaprobatorio (< 11), debe activar alerta roja inmediata: contacto al apoderado en menos de 24 horas y plan de acompañamiento tutorial.'),
('PROT-02', 'ALERTA_TEMPRANA', 'Umbral de Alerta Ámbar Preventiva', 'AMBAR',
 'Estudiantes con índice de riesgo entre 30 y 59 requieren seguimiento preventivo: entrevista individual en la semana, revisión de hábitos de estudio y notificación informativa cordial al apoderado.'),
('PROT-03', 'ALERTA_TEMPRANA', 'Seguimiento Nivel Verde', 'VERDE',
 'Estudiantes con índice de riesgo menor a 30 se mantienen en monitoreo regular y refuerzo positivo de logros y asistencia puntual.'),
('PROT-04', 'ASISTENCIA', 'Protocolo ante 3 Faltas Consecutivas', 'ROJO',
 'Al detectarse 3 faltas seguidas mediante control de ingreso (RFID o lista), el tutor debe registrar una intervención tutorial, comunicarse telefónicamente con el apoderado y verificar factores familiares o de salud.'),
('PROT-05', 'CONVIVENCIA', 'Atención a Aislamiento Socioemocional', 'ROJO',
 'Ante reportes de aislamiento o desmotivación persistente, el tutor realiza escucha activa confidencial, evita exponer al estudiante frente al aula y deriva al equipo de psicología escolar.'),
('PROT-06', 'CONVIVENCIA', 'Mediación ante Conflictos en Aula', 'AMBAR',
 'Los conflictos verbales o disrupciones reiteradas se abordan mediante prácticas restaurativas, acuerdos escritos de convivencia y seguimiento a los 7 días hábiles.'),
('PROT-07', 'ACADEMICO', 'Plan de Refuerzo por Promedio Desaprobatorio', 'ROJO',
 'Cuando el promedio bimestral es menor a 11 en Matemática o Comunicación, se asignan 2 sesiones semanales de refuerzo pedagógico y se informa al apoderado las metas de recuperación.'),
('PROT-08', 'BIBLIOTECA', 'Indicador de Desvinculación en Biblioteca', 'AMBAR',
 'La no devolución de material o devoluciones tardías reiteradas se registran como señal complementaria de organización escolar; nunca implican sanción económica ni prohibición de acceso a libros.'),
('PROT-09', 'COMUNICACION', 'Redacción de Mensajes a Apoderados', 'GENERAL',
 'Todo mensaje al apoderado debe ser empático, claro, sin lenguaje punitivo ni etiquetas negativas, invitando a una reunión de apoyo conjunto para el bienestar del estudiante.'),
('PROT-10', 'PRIVACIDAD', 'Confidencialidad y Permisos de Información', 'GENERAL',
 'Conforme a la Ley N.° 29733, los padres o apoderados solo pueden consultar el resumen académico y de asistencia de su propio hijo. Los registros internos de convivencia y el listado global de riesgo son exclusivos del personal docente y tutoría.'),
('PROT-11', 'TUTORIA', 'Registro Obligatorio de Intervenciones', 'GENERAL',
 'Cada acción tutorial debe quedar registrada con fecha, motivo concreto y acción acordada. Antes de grabar una intervención desde el asistente virtual, el tutor debe confirmar los datos.'),
('PROT-12', 'TUTORIA', 'Derivación Externa Especializada', 'ROJO',
 'Si tras dos intervenciones tutoriales el estudiante mantiene riesgo rojo, el comité de tutoría evalúa derivación a DEMUNA, centro de salud comunitario o UGEL según guía MINEDU.'),
('PROT-13', 'IOT_RFID', 'Uso del Semáforo de Sala de Profesores', 'GENERAL',
 'El tablero semáforo en sala de profesores muestra en tiempo real los estados Rojo, Ámbar y Verde para priorizar atención preventiva; debe ubicarse en zona restringida solo para docentes.'),
('PROT-14', 'REGLAMENTO', 'Tardanzas Reiteradas', 'AMBAR',
 'Tres tardanzas en una quincena generan diálogo formativo con el estudiante y aviso cordial al apoderado para identificar dificultades de traslado.'),
('PROT-15', 'TRANSPARENCIA', 'Uso Responsable de IA en la Escuela (Ley 31814)', 'GENERAL',
 'El asistente SIGE-360 es una herramienta de apoyo predictivo basada en inteligencia artificial; las decisiones finales de acompañamiento siempre corresponden al tutor y equipo directivo.');
