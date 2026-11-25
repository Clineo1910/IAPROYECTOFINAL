# app.py - Aplicación web SIGE-360 en Python (FastAPI + PostgreSQL + Auth RBAC + puente a n8n)
import os
import json
import re
import time
import threading
import uuid
from datetime import datetime
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

RAIZ = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(RAIZ, '.env'))
MCP_AUDIT_FILE = os.path.join(RAIZ, 'agente', 'mcp_audit.jsonl')

N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', 'http://localhost:5678/webhook/agente')
PORT = int(os.environ.get('PORT', '3060'))

# Sesiones activas en memoria: sid -> dict(email, rol, nombre, cargo, alumno_id)
SESIONES: dict[str, dict] = {}

app = FastAPI(title='SIGE-360')


def obtener_conexion():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=int(os.environ.get('PGPORT', '5432')),
        dbname=os.environ.get('PGDATABASE', 'sige360'),
        user=os.environ.get('PGUSER', 'postgres'),
        password=os.environ.get('PGPASSWORD', ''),
    )


def consultar(sql: str, parametros: tuple = ()) -> list[dict]:
    with obtener_conexion() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, parametros)
            filas = [dict(r) for r in cur.fetchall()]
    for f in filas:
        for k, v in list(f.items()):
            if hasattr(v, 'isoformat'):
                f[k] = v.isoformat()
            elif type(v).__name__ == 'Decimal':
                f[k] = float(v)
    return filas


SQL_METRICAS = """
SELECT
  a.id AS alumno_id,
  a.codigo_estudiante,
  a.codigo_rfid,
  a.nombre_completo,
  a.grado,
  a.seccion,
  a.apoderado_nombre,
  a.apoderado_contacto,
  a.telegram_chat_id,
  (SELECT ROUND(AVG(n.nota)::numeric, 2) FROM notas n WHERE n.alumno_id = a.id) AS promedio,
  (SELECT COUNT(*) FROM asistencia s WHERE s.alumno_id = a.id AND s.estado = 'FALTA') AS faltas,
  (SELECT COUNT(*) FROM asistencia s WHERE s.alumno_id = a.id AND s.estado = 'TARDANZA') AS tardanzas,
  (SELECT COUNT(*) FROM incidencias_convivencia i WHERE i.alumno_id = a.id AND i.tipo <> 'RECONOCIMIENTO' AND i.gravedad = 'ALTA') AS inc_alta,
  (SELECT COUNT(*) FROM incidencias_convivencia i WHERE i.alumno_id = a.id AND i.tipo <> 'RECONOCIMIENTO' AND i.gravedad = 'MEDIA') AS inc_media,
  (SELECT COUNT(*) FROM incidencias_convivencia i WHERE i.alumno_id = a.id AND i.tipo <> 'RECONOCIMIENTO' AND i.gravedad = 'BAJA') AS inc_baja,
  (SELECT COUNT(*) FROM biblioteca_uso b WHERE b.alumno_id = a.id AND b.accion = 'NO_DEVUELTO') AS bib_no_devuelto,
  (SELECT COUNT(*) FROM biblioteca_uso b WHERE b.alumno_id = a.id AND b.accion = 'DEVOLUCION_TARDIA') AS bib_tardia
FROM alumnos a
"""


def evaluar_fila(m: dict) -> dict:
    faltas = int(m.get('faltas') or 0)
    tardanzas = int(m.get('tardanzas') or 0)
    promedio = float(m['promedio']) if m.get('promedio') is not None else None
    inc_alta = int(m.get('inc_alta') or 0)
    inc_media = int(m.get('inc_media') or 0)
    inc_baja = int(m.get('inc_baja') or 0)
    bib_no_devuelto = int(m.get('bib_no_devuelto') or 0)
    bib_tardia = int(m.get('bib_tardia') or 0)

    pts_asistencia = min(40, faltas * 10 + tardanzas * 3)
    if promedio is None:
        pts_notas = 0
    elif promedio < 11:
        pts_notas = 30
    elif promedio < 13:
        pts_notas = 18
    elif promedio < 14:
        pts_notas = 10
    else:
        pts_notas = 0

    pts_convivencia = min(20, inc_alta * 12 + inc_media * 7 + inc_baja * 3)
    pts_biblioteca = min(10, bib_no_devuelto * 10 + bib_tardia * 5)
    score = pts_asistencia + pts_notas + pts_convivencia + pts_biblioteca
    nivel = 'ROJO' if score >= 60 else ('AMBAR' if score >= 30 else 'VERDE')

    return {
        'alumno_id': m['alumno_id'],
        'codigo_estudiante': m['codigo_estudiante'],
        'codigo_rfid': m['codigo_rfid'],
        'nombre_completo': m['nombre_completo'],
        'grado': m['grado'],
        'seccion': m['seccion'],
        'apoderado_nombre': m['apoderado_nombre'],
        'apoderado_contacto': m.get('apoderado_contacto', ''),
        'telegram_chat_id': m.get('telegram_chat_id'),
        'indice_riesgo': score,
        'nivel_semaforo': nivel,
        'desglose': {
            'asistencia_pts': pts_asistencia,
            'notas_pts': pts_notas,
            'convivencia_pts': pts_convivencia,
            'biblioteca_pts': pts_biblioteca,
        },
        'metricas': {
            'promedio_notas': promedio,
            'faltas': faltas,
            'tardanzas': tardanzas,
            'incidencias_alta': inc_alta,
            'incidencias_media': inc_media,
            'libros_no_devueltos': bib_no_devuelto,
            'devoluciones_tardias': bib_tardia,
        },
    }


def obtener_usuario_actual(request: Request) -> tuple[str | None, dict | None]:
    sid = request.cookies.get('sige360_sid')
    if sid and sid in SESIONES:
        return sid, SESIONES[sid]
    return None, None


def exigir_tutor(request: Request):
    _, user = obtener_usuario_actual(request)
    if not user:
        return JSONResponse({'error': 'Debes iniciar sesión.'}, status_code=401)
    if user['rol'] != 'tutor':
        return JSONResponse({'error': 'Permiso denegado: acción exclusiva para docentes/tutores.'}, status_code=403)
    return None


class LoginEntrada(BaseModel):
    email: str
    password: str


class ChatEntrada(BaseModel):
    mensaje: str


class RfidScanEntrada(BaseModel):
    alumno_id: int
    estado: str


class NotaEntrada(BaseModel):
    alumno_id: int
    curso: str
    bimestre: int
    nota: float


class NotaLoteItem(BaseModel):
    alumno_id: int
    nota: float


class NotaLoteEntrada(BaseModel):
    curso: str
    bimestre: int
    calificaciones: list[NotaLoteItem]


class IncidenciaEntrada(BaseModel):
    alumno_id: int
    tipo: str
    gravedad: str
    descripcion: str


class BibliotecaEntrada(BaseModel):
    alumno_id: int
    accion: str
    libro: str


class AlumnoEntrada(BaseModel):
    nombre_completo: str
    grado: str
    seccion: str
    apoderado_nombre: str


class IntervencionEstadoEntrada(BaseModel):
    estado: str


class UsuarioNuevoEntrada(BaseModel):
    email: str
    password: str
    rol: str = 'padre'
    nombre: str
    alumno_id: int | None = None
    telegram_chat_id: str | None = None


class AlertaTelegramEntrada(BaseModel):
    alumno_id: int | None = None
    mensaje: str


# ==================== AUTENTICACIÓN (DESDE POSTGRESQL) ====================
@app.post('/api/login')
def api_login(entrada: LoginEntrada, response: Response):
    email = entrada.email.strip().lower()
    filas = consultar(
        "SELECT id, email, password, rol, nombre, cargo, alumno_id FROM usuarios WHERE LOWER(email) = %s LIMIT 1",
        (email,),
    )
    if not filas or filas[0]['password'] != entrada.password:
        return JSONResponse({'error': 'Correo o contraseña incorrectos.'}, status_code=401)

    cuenta = filas[0]
    sid = uuid.uuid4().hex
    SESIONES[sid] = {
        'id': cuenta['id'],
        'email': cuenta['email'],
        'rol': cuenta['rol'],
        'nombre': cuenta['nombre'],
        'cargo': cuenta['cargo'],
        'alumno_id': cuenta['alumno_id'],
    }
    response.set_cookie('sige360_sid', sid, httponly=True, max_age=28800, samesite='lax')
    destino = '/padres.html' if cuenta['rol'] == 'padre' else '/'
    return {'ok': True, 'usuario': SESIONES[sid], 'redirect': destino}


@app.post('/api/logout')
def api_logout(request: Request, response: Response):
    sid = request.cookies.get('sige360_sid')
    if sid and sid in SESIONES:
        del SESIONES[sid]
    response.delete_cookie('sige360_sid')
    return {'ok': True, 'redirect': '/login.html'}


@app.get('/api/me')
def api_me(request: Request):
    sid, user = obtener_usuario_actual(request)
    if not user:
        return JSONResponse({'autenticado': False}, status_code=401)
    return {'autenticado': True, 'sesion': sid, 'usuario': user}


# ==================== PORTAL DE PADRES (SOLO SU HIJO) ====================
@app.get('/api/mi-hijo')
def api_mi_hijo(request: Request):
    _, user = obtener_usuario_actual(request)
    if not user:
        return JSONResponse({'error': 'No autenticado'}, status_code=401)
    alumno_id = user.get('alumno_id') or 3
    try:
        filas = consultar(f"{SQL_METRICAS} WHERE a.id = %s LIMIT 1", (alumno_id,))
        if not filas:
            return JSONResponse({'error': 'Estudiante no encontrado'}, status_code=404)
        perfil = evaluar_fila(filas[0])
        notas = consultar(
            "SELECT curso, bimestre, nota, fecha_registro FROM notas WHERE alumno_id = %s ORDER BY bimestre DESC, curso ASC",
            (alumno_id,),
        )
        asistencia = consultar(
            "SELECT fecha, estado, hora_rfid, origen FROM asistencia WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 12",
            (alumno_id,),
        )
        # Solo avisos/intervenciones públicas de seguimiento, sin incidencias confidenciales internas
        avisos = consultar(
            "SELECT fecha, tutor_nombre, accion_acordada, estado FROM intervenciones_tutoriales WHERE alumno_id = %s ORDER BY id DESC LIMIT 5",
            (alumno_id,),
        )
        alertas = consultar(
            "SELECT fecha, canal, mensaje, detalle_estado FROM alertas_enviadas WHERE alumno_id = %s OR alumno_id IS NULL ORDER BY id DESC LIMIT 5",
            (alumno_id,),
        )
        return {
            'apoderado': user['nombre'],
            'alumno': {
                'alumno_id': perfil['alumno_id'],
                'codigo_estudiante': perfil['codigo_estudiante'],
                'nombre_completo': perfil['nombre_completo'],
                'grado': perfil['grado'],
                'seccion': perfil['seccion'],
                'nivel_semaforo': perfil['nivel_semaforo'],
                'promedio_notas': perfil['metricas']['promedio_notas'],
                'faltas': perfil['metricas']['faltas'],
                'tardanzas': perfil['metricas']['tardanzas'],
            },
            'notas': notas,
            'asistencia': asistencia,
            'avisos_tutor': avisos,
            'alertas_recibidas': alertas,
        }
    except Exception as exc:
        print('[APP] Error /api/mi-hijo:', exc)
        return JSONResponse({'error': 'Error cargando información del estudiante'}, status_code=500)


# ==================== ENDPOINTS DOCENTES / IoT ====================
@app.get('/api/mcp-logs')
def api_mcp_logs():
    if not os.path.exists(MCP_AUDIT_FILE):
        return {'logs': []}
    try:
        with open(MCP_AUDIT_FILE, 'r', encoding='utf-8') as f:
            lineas = [l.strip() for l in f if l.strip()]
        eventos = [json.loads(l) for l in lineas[-12:]]
        eventos.reverse()
        return {'logs': eventos}
    except Exception:
        return {'logs': []}


@app.get('/api/dashboard')
def api_dashboard():
    # Accesible por Portal Docente y por la pantalla IoT de Sala de Profesores
    try:
        filas = consultar(f"{SQL_METRICAS} ORDER BY a.id ASC LIMIT 50")
        alumnos = [evaluar_fila(f) for f in filas]
        alumnos.sort(key=lambda x: (-x['indice_riesgo'], x['alumno_id']))
        resumen = {
            'total': len(alumnos),
            'rojo': sum(1 for a in alumnos if a['nivel_semaforo'] == 'ROJO'),
            'ambar': sum(1 for a in alumnos if a['nivel_semaforo'] == 'AMBAR'),
            'verde': sum(1 for a in alumnos if a['nivel_semaforo'] == 'VERDE'),
            'promedio_riesgo': round(sum(a['indice_riesgo'] for a in alumnos) / max(1, len(alumnos)), 1),
        }
        ultimos_rfid = consultar(
            """SELECT s.id, a.nombre_completo, a.codigo_rfid, a.grado, a.seccion,
                      s.fecha, s.estado, s.hora_rfid, s.origen
               FROM asistencia s JOIN alumnos a ON a.id = s.alumno_id
               ORDER BY s.fecha DESC, s.id DESC LIMIT 10"""
        )
        intervenciones = consultar(
            """SELECT i.id, i.alumno_id, a.nombre_completo, a.grado, a.seccion,
                      i.fecha, i.tutor_nombre, i.motivo, i.accion_acordada, i.estado
               FROM intervenciones_tutoriales i JOIN alumnos a ON a.id = i.alumno_id
               ORDER BY i.id DESC LIMIT 15"""
        )
        return {
            'resumen': resumen,
            'alumnos': alumnos,
            'ultimos_rfid': ultimos_rfid,
            'intervenciones': intervenciones,
        }
    except Exception as exc:
        print('[APP] Error cargando dashboard:', exc)
        return JSONResponse({'error': 'No se pudo conectar con PostgreSQL.'}, status_code=500)


@app.get('/api/alumno/{alumno_id}')
def api_alumno_detalle(alumno_id: int, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    try:
        filas = consultar(f"{SQL_METRICAS} WHERE a.id = %s LIMIT 1", (alumno_id,))
        if not filas:
            return JSONResponse({'error': 'Alumno no encontrado'}, status_code=404)
        perfil = evaluar_fila(filas[0])
        notas = consultar(
            "SELECT curso, bimestre, nota, fecha_registro FROM notas WHERE alumno_id = %s ORDER BY fecha_registro DESC LIMIT 12",
            (alumno_id,),
        )
        asistencia = consultar(
            "SELECT fecha, estado, hora_rfid, origen FROM asistencia WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 10",
            (alumno_id,),
        )
        incidencias = consultar(
            "SELECT fecha, tipo, gravedad, descripcion FROM incidencias_convivencia WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 10",
            (alumno_id,),
        )
        biblioteca = consultar(
            "SELECT fecha, accion, libro FROM biblioteca_uso WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 10",
            (alumno_id,),
        )
        intervenciones = consultar(
            "SELECT id, fecha, tutor_nombre, motivo, accion_acordada, estado FROM intervenciones_tutoriales WHERE alumno_id = %s ORDER BY id DESC LIMIT 10",
            (alumno_id,),
        )
        return {
            'perfil': perfil,
            'notas': notas,
            'asistencia': asistencia,
            'incidencias': incidencias,
            'biblioteca': biblioteca,
            'intervenciones': intervenciones,
        }
    except Exception as exc:
        print('[APP] Error detalle alumno:', exc)
        return JSONResponse({'error': 'Error cargando ficha del alumno'}, status_code=500)


@app.get('/api/protocolos')
def api_protocolos():
    try:
        filas = consultar(
            "SELECT codigo, categoria, titulo, nivel_riesgo, contenido FROM protocolos_minedu ORDER BY codigo ASC"
        )
        return {'protocolos': filas}
    except Exception as exc:
        print('[APP] Error cargando protocolos:', exc)
        return JSONResponse({'error': 'Error cargando protocolos'}, status_code=500)


@app.post('/api/rfid-scan')
def api_rfid_scan(entrada: RfidScanEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    estado = entrada.estado.upper().strip()
    if estado not in ('PRESENTE', 'TARDANZA', 'FALTA'):
        return JSONResponse({'error': 'Estado RFID inválido'}, status_code=400)
    ahora = datetime.now()
    hora_rfid = None if estado == 'FALTA' else ahora.strftime('%H:%M:%S')
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO asistencia (alumno_id, fecha, estado, hora_rfid, origen)
                       VALUES (%s, %s, %s, %s, 'RFID_PUERTA')""",
                    (entrada.alumno_id, ahora.strftime('%Y-%m-%d'), estado, hora_rfid),
                )
            conn.commit()
        return {'ok': True, 'mensaje': f'Lectura RFID registrada: alumno ID {entrada.alumno_id} → {estado}.'}
    except Exception as exc:
        print('[APP] Error escáner RFID:', exc)
        return JSONResponse({'error': 'No se pudo registrar lectura RFID'}, status_code=500)


@app.get('/api/notas')
def api_listar_notas(request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    try:
        filas = consultar(
            """SELECT n.id, n.alumno_id, a.nombre_completo, a.grado, a.seccion,
                      n.curso, n.bimestre, n.nota, n.fecha_registro
               FROM notas n JOIN alumnos a ON a.id = n.alumno_id
               ORDER BY n.id DESC LIMIT 160"""
        )
        return {'notas': filas}
    except Exception as exc:
        print('[APP] Error listando notas:', exc)
        return JSONResponse({'error': 'No se pudieron cargar las notas'}, status_code=500)


@app.post('/api/notas/lote')
def api_crear_notas_lote(entrada: NotaLoteEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    if entrada.bimestre not in (1, 2, 3, 4) or not entrada.calificaciones:
        return JSONResponse({'error': 'Bimestre o lista de calificaciones inválidos.'}, status_code=400)
    try:
        hoy = datetime.now().strftime('%Y-%m-%d')
        curso = entrada.curso.strip()
        guardadas = 0
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                for item in entrada.calificaciones:
                    if item.nota < 0 or item.nota > 20:
                        continue
                    cur.execute(
                        "DELETE FROM notas WHERE alumno_id = %s AND curso = %s AND bimestre = %s",
                        (item.alumno_id, curso, entrada.bimestre),
                    )
                    cur.execute(
                        """INSERT INTO notas (alumno_id, curso, bimestre, nota, fecha_registro)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (item.alumno_id, curso, entrada.bimestre, round(item.nota, 2), hoy),
                    )
                    guardadas += 1
            conn.commit()
        return {
            'ok': True,
            'guardadas': guardadas,
            'mensaje': f'Acta guardada: {guardadas} calificaciones de {curso} (Bimestre {entrada.bimestre}) actualizadas en PostgreSQL.',
        }
    except Exception as exc:
        print('[APP] Error guardando acta por lote:', exc)
        return JSONResponse({'error': 'No se pudo guardar el acta de calificaciones'}, status_code=500)


@app.get('/api/convivencia')
def api_listar_convivencia(request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    try:
        incidencias = consultar(
            """SELECT i.id, i.alumno_id, a.nombre_completo, a.grado, a.seccion,
                      i.fecha, i.tipo, i.gravedad, i.descripcion
               FROM incidencias_convivencia i JOIN alumnos a ON a.id = i.alumno_id
               ORDER BY i.id DESC LIMIT 30"""
        )
        biblioteca = consultar(
            """SELECT b.id, b.alumno_id, a.nombre_completo, a.grado, a.seccion,
                      b.fecha, b.accion, b.libro
               FROM biblioteca_uso b JOIN alumnos a ON a.id = b.alumno_id
               ORDER BY b.id DESC LIMIT 30"""
        )
        return {'incidencias': incidencias, 'biblioteca': biblioteca}
    except Exception as exc:
        print('[APP] Error listando convivencia/biblioteca:', exc)
        return JSONResponse({'error': 'No se pudieron cargar los registros'}, status_code=500)


@app.post('/api/incidencias')
def api_crear_incidencia(entrada: IncidenciaEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    tipo = entrada.tipo.upper().strip()
    gravedad = entrada.gravedad.upper().strip()
    if tipo not in ('DISRUPCION', 'CONFLICTO', 'AISLAMIENTO', 'RECONOCIMIENTO') or gravedad not in ('BAJA', 'MEDIA', 'ALTA'):
        return JSONResponse({'error': 'Tipo o gravedad inválidos.'}, status_code=400)
    try:
        hoy = datetime.now().strftime('%Y-%m-%d')
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO incidencias_convivencia (alumno_id, fecha, tipo, gravedad, descripcion)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (entrada.alumno_id, hoy, tipo, gravedad, entrada.descripcion.strip()[:250]),
                )
                creado = cur.fetchone()
            conn.commit()
        return {'ok': True, 'id': creado['id'], 'mensaje': f'Incidencia ({tipo} · {gravedad}) registrada y score actualizado.'}
    except Exception as exc:
        print('[APP] Error registrando incidencia:', exc)
        return JSONResponse({'error': 'No se pudo registrar la incidencia'}, status_code=500)


@app.post('/api/biblioteca')
def api_crear_biblioteca(entrada: BibliotecaEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    accion = entrada.accion.upper().strip()
    if accion not in ('PRESTAMO', 'LECTURA_SALA', 'DEVOLUCION_TARDIA', 'NO_DEVUELTO'):
        return JSONResponse({'error': 'Acción de biblioteca inválida.'}, status_code=400)
    try:
        hoy = datetime.now().strftime('%Y-%m-%d')
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO biblioteca_uso (alumno_id, fecha, accion, libro)
                       VALUES (%s, %s, %s, %s) RETURNING id""",
                    (entrada.alumno_id, hoy, accion, entrada.libro.strip()[:115]),
                )
                creado = cur.fetchone()
            conn.commit()
        return {'ok': True, 'id': creado['id'], 'mensaje': f'Movimiento de biblioteca ({accion}) registrado.'}
    except Exception as exc:
        print('[APP] Error registrando biblioteca:', exc)
        return JSONResponse({'error': 'No se pudo registrar movimiento de biblioteca'}, status_code=500)


@app.post('/api/alumnos')
def api_crear_alumno(entrada: AlumnoEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    nombre = entrada.nombre_completo.strip()
    if len(nombre) < 4:
        return JSONResponse({'error': 'Ingrese nombre y apellido del estudiante.'}, status_code=400)
    try:
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS sig FROM alumnos")
                sig = int(cur.fetchone()['sig'])
                codigo = f"EST-2026-{sig:03d}"
                rfid = f"RFID-A{100 + sig}"
                contacto = f"apoderado{sig:02d}@demo.sige360.local"
                cur.execute(
                    """INSERT INTO alumnos (codigo_estudiante, codigo_rfid, nombre_completo, grado, seccion, apoderado_nombre, apoderado_contacto)
                       VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, codigo_estudiante, codigo_rfid""",
                    (codigo, rfid, nombre, entrada.grado.strip(), entrada.seccion.strip()[:1].upper(), entrada.apoderado_nombre.strip() or 'Apoderado (Demo)', contacto),
                )
                creado = dict(cur.fetchone())
            conn.commit()
        return {'ok': True, 'alumno': creado, 'mensaje': f'Estudiante {nombre} matriculado ({codigo} · {rfid}).'}
    except Exception as exc:
        print('[APP] Error creando alumno:', exc)
        return JSONResponse({'error': 'No se pudo registrar el estudiante'}, status_code=500)


@app.patch('/api/intervenciones/{intervencion_id}')
def api_actualizar_intervencion(intervencion_id: int, entrada: IntervencionEstadoEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    estado = entrada.estado.upper().strip()
    if estado not in ('PROGRAMADA', 'SEGUIMIENTO', 'REALIZADA'):
        return JSONResponse({'error': 'Estado inválido'}, status_code=400)
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE intervenciones_tutoriales SET estado = %s WHERE id = %s",
                    (estado, intervencion_id),
                )
            conn.commit()
        return {'ok': True, 'estado': estado}
    except Exception as exc:
        print('[APP] Error actualizando intervención:', exc)
        return JSONResponse({'error': 'No se pudo actualizar estado'}, status_code=500)


@app.post('/api/simular-rfid')
def api_simular_rfid(request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    alumno_id = 3  # Lucas Mendoza Paredes
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM asistencia WHERE alumno_id = %s AND fecha >= '2026-11-23'", (alumno_id,))
                cur.execute("DELETE FROM notas WHERE alumno_id = %s AND fecha_registro >= '2026-11-23'", (alumno_id,))
                cur.execute(
                    """INSERT INTO asistencia (alumno_id, fecha, estado, hora_rfid, origen) VALUES
                       (%s, '2026-11-23', 'FALTA', NULL, 'RFID_PUERTA'),
                       (%s, '2026-11-24', 'FALTA', NULL, 'RFID_PUERTA'),
                       (%s, '2026-11-25', 'FALTA', NULL, 'RFID_PUERTA')""",
                    (alumno_id, alumno_id, alumno_id),
                )
                cur.execute(
                    "INSERT INTO notas (alumno_id, curso, bimestre, nota, fecha_registro) VALUES (%s, 'Matemática', 4, 6.00, '2026-11-25')",
                    (alumno_id,),
                )
            conn.commit()
        return {
            'ok': True,
            'mensaje': 'Evento RFID simulado: 3 faltas consecutivas + nota 06 en Matemática para Lucas Mendoza Paredes.',
            'prompt_sugerido': 'Alerta automática RFID: evalúa el índice de riesgo actual de Lucas Mendoza (ID 3), indica qué protocolo MINEDU aplica ante 3 faltas consecutivas y redacta un mensaje empático sugerido para su apoderado.',
        }
    except Exception as exc:
        print('[APP] Error simulador RFID:', exc)
        return JSONResponse({'error': 'No se pudo ejecutar la simulación RFID.'}, status_code=500)


@app.post('/api/reset-demo')
def api_reset_demo(request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    alumno_id = 3
    with obtener_conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM asistencia WHERE alumno_id = %s AND fecha >= '2026-11-23'", (alumno_id,))
            cur.execute("DELETE FROM notas WHERE alumno_id = %s AND fecha_registro >= '2026-11-23'", (alumno_id,))
        conn.commit()
    return {'ok': True, 'mensaje': 'Demo reiniciada: Lucas Mendoza volvió a su estado base (ÁMBAR).'}


@app.post('/api/chat')
def api_chat(entrada: ChatEntrada, request: Request):
    sid, user = obtener_usuario_actual(request)
    if not user:
        return JSONResponse({'respuesta': 'Tu sesión expiró. Inicia sesión nuevamente.'}, status_code=401)
    mensaje = entrada.mensaje.strip()
    if not mensaje or len(mensaje) > 500:
        return {'respuesta': 'Escriba una consulta de hasta 500 caracteres.'}

    rol = user['rol']
    if rol == 'padre':
        aid = user.get('alumno_id') or 3
        al = consultar("SELECT nombre_completo FROM alumnos WHERE id = %s LIMIT 1", (aid,))
        nom_hijo = al[0]['nombre_completo'] if al else f'ID {aid}'
        mensaje_enviado = f"(Apoderado autenticado: {user['nombre']}, solo autorizado para su hijo {nom_hijo} ID {aid}) {mensaje}"
    else:
        mensaje_enviado = mensaje

    try:
        r = requests.post(
            N8N_WEBHOOK_URL,
            json={'sesion': sid, 'rol': rol, 'mensaje': mensaje_enviado},
            timeout=60,
        )
        if not r.ok:
            print(f'[CHAT] n8n respondió HTTP {r.status_code}')
            return {'respuesta': 'El asistente no está disponible en este momento (verifica que el flujo de n8n esté activo).'}
        datos = r.json()
        texto = (datos.get('respuesta') or '').strip()
        return {'respuesta': texto or 'No pude elaborar una respuesta. Intente con otra pregunta.'}
    except Exception as exc:
        print('[CHAT] Error conectando con n8n:', exc)
        return {'respuesta': 'El asistente no está disponible. Verifique que n8n y el servidor MCP estén encendidos.'}


# ==================== USUARIOS (CUENTAS DE PADRES Y DOCENTES) ====================
@app.get('/api/usuarios')
def api_listar_usuarios(request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    filas = consultar(
        """SELECT u.id, u.email, u.rol, u.nombre, u.cargo, u.alumno_id, a.nombre_completo AS alumno_nombre
           FROM usuarios u LEFT JOIN alumnos a ON a.id = u.alumno_id
           ORDER BY u.id DESC LIMIT 50"""
    )
    return {'usuarios': filas}


@app.post('/api/usuarios')
def api_crear_usuario(entrada: UsuarioNuevoEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    email = entrada.email.strip().lower()
    rol = entrada.rol.strip().lower()
    if '@' not in email or len(entrada.password) < 4 or rol not in ('padre', 'tutor'):
        return JSONResponse({'error': 'Correo válido, contraseña (mín. 4 caracteres) y rol requeridos.'}, status_code=400)
    if rol == 'padre' and not entrada.alumno_id:
        return JSONResponse({'error': 'Para crear una cuenta de padre debes seleccionar a su hijo/a.'}, status_code=400)

    cargo = 'Docente / Tutor SIGE-360'
    if rol == 'padre':
        al = consultar("SELECT nombre_completo, grado, seccion FROM alumnos WHERE id = %s LIMIT 1", (entrada.alumno_id,))
        if not al:
            return JSONResponse({'error': 'Estudiante no encontrado.'}, status_code=404)
        cargo = f"Apoderado de {al[0]['nombre_completo']} ({al[0]['grado']} {al[0]['seccion']})"

    try:
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO usuarios (email, password, rol, nombre, cargo, alumno_id)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, email, rol, nombre, cargo""",
                    (email, entrada.password, rol, entrada.nombre.strip(), cargo, entrada.alumno_id if rol == 'padre' else None),
                )
                creado = dict(cur.fetchone())
                if rol == 'padre' and entrada.alumno_id and entrada.telegram_chat_id and entrada.telegram_chat_id.strip():
                    cur.execute(
                        "UPDATE alumnos SET telegram_chat_id = %s WHERE id = %s",
                        (entrada.telegram_chat_id.strip(), entrada.alumno_id),
                    )
            conn.commit()
        return {'ok': True, 'usuario': creado, 'mensaje': f'Cuenta creada ({email} · rol {rol}). Ya puede iniciar sesión en /login.html.'}
    except Exception as exc:
        print('[APP] Error creando usuario:', exc)
        return JSONResponse({'error': 'Ese correo ya está registrado o hubo un error al guardar.'}, status_code=400)


# ==================== ALERTAS TELEGRAM (API EXTERNA GRATIS - PASO 5) ====================
@app.post('/api/alertas/telegram')
def api_enviar_telegram(entrada: AlertaTelegramEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    texto = entrada.mensaje.strip()
    if not texto:
        return JSONResponse({'error': 'El mensaje no puede estar vacío.'}, status_code=400)

    # Recarga .env por si el usuario acaba de pegar su token de @BotFather
    load_dotenv(os.path.join(RAIZ, '.env'), override=True)
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    chat_id_destino = os.environ.get('TELEGRAM_CHAT_ID', '').strip()
    origen_destino = 'chat demo (.env)'

    # Si el alumno tiene su propio apoderado vinculado en PostgreSQL, usar ese chat_id
    if entrada.alumno_id:
        filas_tg = consultar(
            "SELECT nombre_completo, telegram_chat_id FROM alumnos WHERE id = %s LIMIT 1",
            (entrada.alumno_id,),
        )
        if filas_tg and filas_tg[0].get('telegram_chat_id'):
            chat_id_destino = str(filas_tg[0]['telegram_chat_id']).strip()
            origen_destino = f"apoderado vinculado de {filas_tg[0]['nombre_completo']}"

    enviado_externo = False
    detalle = 'Guardado en Portal de Padres (configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env para envío al celular).'

    if token and chat_id_destino:
        try:
            r = requests.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json={'chat_id': chat_id_destino, 'text': f'🏫 SIGE-360 · Alerta al Apoderado\n\n{texto}'},
                timeout=10,
            )
            r.raise_for_status()
            enviado_externo = True
            detalle = f'Enviado en vivo por Telegram ({origen_destino}) y publicado en Portal de Padres.'
        except Exception as exc:
            print('[TELEGRAM] Error:', exc)
            detalle = 'Guardado en Portal de Padres (Telegram no respondió; verifica tu token/chat_id).'

    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO alertas_enviadas (alumno_id, canal, mensaje, enviado_externo, detalle_estado)
                       VALUES (%s, 'TELEGRAM', %s, %s, %s)""",
                    (entrada.alumno_id, texto[:1500], enviado_externo, detalle),
                )
            conn.commit()
    except Exception as exc:
        print('[APP] Error guardando alerta:', exc)

    return {'ok': True, 'enviado_telegram': enviado_externo, 'mensaje': detalle}


# ==================== AUTO-VINCULACIÓN DE PADRES VÍA TELEGRAM BOT ====================
def _bucle_vinculacion_telegram():
    """Escucha mensajes a @SIGE360_Alertas_Bot para vincular padres por código de estudiante (ej. EST-2026-003)."""
    offset = 0
    # Descarta mensajes antiguos al arrancar
    load_dotenv(os.path.join(RAIZ, '.env'), override=True)
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        return
    try:
        init = requests.get(f'https://api.telegram.org/bot{token}/getUpdates', timeout=8).json()
        res = init.get('result', [])
        if res:
            offset = res[-1]['update_id'] + 1
    except Exception:
        pass

    patron_codigo = re.compile(r'EST-\d{4}-\d{3}', re.IGNORECASE)
    while True:
        try:
            resp = requests.get(
                f'https://api.telegram.org/bot{token}/getUpdates',
                params={'offset': offset, 'timeout': 5},
                timeout=10,
            ).json()
            for upd in resp.get('result', []):
                offset = upd['update_id'] + 1
                msg = upd.get('message') or {}
                chat_id = (msg.get('chat') or {}).get('id')
                texto = (msg.get('text') or '').strip()
                if not chat_id or not texto:
                    continue

                match = patron_codigo.search(texto)
                if match:
                    codigo = match.group(0).upper()
                    filas = consultar(
                        "SELECT id, nombre_completo, grado, seccion FROM alumnos WHERE UPPER(codigo_estudiante) = %s LIMIT 1",
                        (codigo,),
                    )
                    if filas:
                        al = filas[0]
                        with obtener_conexion() as conn:
                            with conn.cursor() as cur:
                                cur.execute(
                                    "UPDATE alumnos SET telegram_chat_id = %s WHERE id = %s",
                                    (str(chat_id), al['id']),
                                )
                            conn.commit()
                        respuesta_bot = (
                            f"✅ ¡Vinculación exitosa!\n"
                            f"Tu Telegram (ID {chat_id}) quedó asociado al estudiante:\n"
                            f"• {al['nombre_completo']} ({codigo} · {al['grado']} {al['seccion']})\n\n"
                            f"Recibirás aquí las alertas tempranas de asistencia y rendimiento de SIGE-360."
                        )
                    else:
                        respuesta_bot = f"⚠️ No encontramos ningún estudiante con el código {codigo}. Verifica el código (ej. EST-2026-003)."
                else:
                    respuesta_bot = (
                        "🏫 Bienvenido a SIGE-360 Alertas.\n"
                        "Para vincular tu celular con tu hijo/a, envíame su código de estudiante (ejemplo: EST-2026-003).\n"
                        "Por protección de datos (Ley N.° 29733), usamos códigos escolares simulados y no DNIs reales."
                    )

                requests.post(
                    f'https://api.telegram.org/bot{token}/sendMessage',
                    json={'chat_id': chat_id, 'text': respuesta_bot},
                    timeout=8,
                )
        except Exception:
            time.sleep(4)
        time.sleep(2)


@app.on_event('startup')
def iniciar_listener_telegram():
    hilo = threading.Thread(target=_bucle_vinculacion_telegram, daemon=True)
    hilo.start()


# ==================== RUTAS PROTEGIDAS DE PÁGINAS (MULTIPÁGINA REAL) ====================
PUBLIC_DIR = os.path.join(RAIZ, 'public')


def servir_pagina_docente(request: Request, archivo: str):
    _, user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse('/login.html', status_code=302)
    if user['rol'] == 'padre':
        return RedirectResponse('/padres.html', status_code=302)
    return FileResponse(os.path.join(PUBLIC_DIR, archivo))


@app.get('/')
def ruta_inicio(request: Request):
    return servir_pagina_docente(request, 'index.html')


@app.get('/notas.html')
def ruta_notas(request: Request):
    return servir_pagina_docente(request, 'notas.html')


@app.get('/convivencia.html')
def ruta_convivencia(request: Request):
    return servir_pagina_docente(request, 'convivencia.html')


@app.get('/biblioteca.html')
def ruta_biblioteca(request: Request):
    return servir_pagina_docente(request, 'biblioteca.html')


@app.get('/intervenciones.html')
def ruta_intervenciones(request: Request):
    return servir_pagina_docente(request, 'intervenciones.html')


@app.get('/usuarios.html')
def ruta_usuarios(request: Request):
    return servir_pagina_docente(request, 'usuarios.html')


@app.get('/protocolos.html')
def ruta_protocolos(request: Request):
    return servir_pagina_docente(request, 'protocolos.html')


@app.get('/padres.html')
def servir_padres(request: Request):
    _, user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse('/login.html', status_code=302)
    return FileResponse(os.path.join(PUBLIC_DIR, 'padres.html'))


app.mount('/', StaticFiles(directory=PUBLIC_DIR), name='public')
