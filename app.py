# app.py - Aplicación web SIGE-360 en Python (FastAPI + PostgreSQL + Auth RBAC + puente a n8n)
import os
import json
import re
import hmac
import hashlib
import secrets
import time
import html
import threading
import unicodedata
from datetime import datetime, timedelta
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
COOKIE_SECURE = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'
IOT_DISPLAY_KEY = os.environ.get('IOT_DISPLAY_KEY', '').strip()

app = FastAPI(title='SIGE-360')


@app.middleware('http')
async def cabeceras_seguridad(request: Request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'same-origin'
    return response


def hashear_password(pwd: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pwd.encode('utf-8'), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${dk.hex()}"


def verificar_password(pwd: str, almacenado: str) -> bool:
    if not almacenado:
        return False
    if almacenado.startswith('scrypt$'):
        partes = almacenado.split('$')
        if len(partes) != 3:
            return False
        salt = bytes.fromhex(partes[1])
        esperado = bytes.fromhex(partes[2])
        actual = hashlib.scrypt(pwd.encode('utf-8'), salt=salt, n=16384, r=8, p=1)
        return hmac.compare_digest(actual, esperado)
    return hmac.compare_digest(pwd, almacenado)


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
    if not sid:
        return None, None
    try:
        filas = consultar(
            """SELECT u.id, u.email, u.rol, u.nombre, u.cargo, u.alumno_id
               FROM sesiones_activas s JOIN usuarios u ON u.id = s.usuario_id
               WHERE s.sid = %s AND s.expira_en > CURRENT_TIMESTAMP
               LIMIT 1""",
            (sid,),
        )
        if filas:
            return sid, filas[0]
    except Exception:
        pass
    return None, None


def tiene_acceso_iot_o_tutor(request: Request) -> bool:
    _, user = obtener_usuario_actual(request)
    if user and user['rol'] == 'tutor':
        return True
    iot_key = (request.query_params.get('iot_key') or request.headers.get('X-IOT-Key') or '').strip()
    if IOT_DISPLAY_KEY and iot_key and hmac.compare_digest(iot_key, IOT_DISPLAY_KEY):
        return True
    return False


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


class AlumnoEditarEntrada(BaseModel):
    nombre_completo: str
    grado: str
    seccion: str
    apoderado_nombre: str
    apoderado_contacto: str = ''
    telegram_chat_id: str | None = None


class IntervencionEstadoEntrada(BaseModel):
    estado: str


class UsuarioNuevoEntrada(BaseModel):
    email: str
    password: str
    rol: str = 'padre'
    nombre: str
    alumno_id: int | None = None
    telegram_chat_id: str | None = None


class UsuarioEditarEntrada(BaseModel):
    email: str
    nombre: str
    rol: str = 'padre'
    password: str | None = None
    alumno_id: int | None = None
    telegram_chat_id: str | None = None


class AlertaTelegramEntrada(BaseModel):
    alumno_id: int | None = None
    mensaje: str


# ==================== AUTENTICACIÓN (SCRYPT + SESIONES PERSISTENTES EN POSTGRESQL) ====================
@app.post('/api/login')
def api_login(entrada: LoginEntrada, response: Response):
    email = entrada.email.strip().lower()
    filas = consultar(
        "SELECT id, email, password, rol, nombre, cargo, alumno_id FROM usuarios WHERE LOWER(email) = %s LIMIT 1",
        (email,),
    )
    if not filas or not verificar_password(entrada.password, filas[0]['password']):
        return JSONResponse({'error': 'Correo o contraseña incorrectos.'}, status_code=401)

    cuenta = filas[0]
    sid = secrets.token_hex(32)
    expira = datetime.now() + timedelta(hours=8)
    with obtener_conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sesiones_activas WHERE expira_en <= CURRENT_TIMESTAMP")
            cur.execute(
                "INSERT INTO sesiones_activas (sid, usuario_id, expira_en) VALUES (%s, %s, %s)",
                (sid, cuenta['id'], expira),
            )
        conn.commit()

    usuario_pub = {
        'id': cuenta['id'],
        'email': cuenta['email'],
        'rol': cuenta['rol'],
        'nombre': cuenta['nombre'],
        'cargo': cuenta['cargo'],
        'alumno_id': cuenta['alumno_id'],
    }
    response.set_cookie('sige360_sid', sid, httponly=True, secure=COOKIE_SECURE, max_age=28800, samesite='lax')
    destino = '/padres.html' if cuenta['rol'] == 'padre' else '/'
    return {'ok': True, 'usuario': usuario_pub, 'redirect': destino}


@app.post('/api/logout')
def api_logout(request: Request, response: Response):
    sid = request.cookies.get('sige360_sid')
    if sid:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sesiones_activas WHERE sid = %s", (sid,))
            conn.commit()
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
def api_mcp_logs(request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
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
def api_dashboard(request: Request):
    if not tiene_acceso_iot_o_tutor(request):
        return JSONResponse({'error': 'Acceso restringido a personal docente o pantalla IoT autorizada.'}, status_code=403)
    try:
        filas = consultar(f"{SQL_METRICAS} ORDER BY a.id ASC LIMIT 120")
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


@app.put('/api/alumnos/{alumno_id}')
def api_editar_alumno(alumno_id: int, entrada: AlumnoEditarEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    nombre = entrada.nombre_completo.strip()
    if len(nombre) < 4:
        return JSONResponse({'error': 'El nombre del estudiante es obligatorio.'}, status_code=400)
    tg = (entrada.telegram_chat_id or '').strip() or None
    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE alumnos
                       SET nombre_completo = %s, grado = %s, seccion = %s,
                           apoderado_nombre = %s, apoderado_contacto = %s, telegram_chat_id = %s
                       WHERE id = %s""",
                    (
                        nombre,
                        entrada.grado.strip(),
                        entrada.seccion.strip()[:1].upper(),
                        entrada.apoderado_nombre.strip() or 'Apoderado (Demo)',
                        entrada.apoderado_contacto.strip(),
                        tg,
                        alumno_id,
                    ),
                )
            conn.commit()
        return {'ok': True, 'mensaje': f'Datos de {nombre} actualizados en PostgreSQL.'}
    except Exception as exc:
        print('[APP] Error editando alumno:', exc)
        return JSONResponse({'error': 'No se pudo actualizar el estudiante'}, status_code=500)


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
        """SELECT u.id, u.email, u.rol, u.nombre, u.cargo, u.alumno_id,
                  a.nombre_completo AS alumno_nombre, a.telegram_chat_id
           FROM usuarios u LEFT JOIN alumnos a ON a.id = u.alumno_id
           ORDER BY u.id DESC LIMIT 80"""
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
                    (email, hashear_password(entrada.password), rol, entrada.nombre.strip(), cargo, entrada.alumno_id if rol == 'padre' else None),
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


@app.put('/api/usuarios/{usuario_id}')
def api_editar_usuario(usuario_id: int, entrada: UsuarioEditarEntrada, request: Request):
    bloqueo = exigir_tutor(request)
    if bloqueo:
        return bloqueo
    email = entrada.email.strip().lower()
    rol = entrada.rol.strip().lower()
    if '@' not in email or rol not in ('padre', 'tutor'):
        return JSONResponse({'error': 'Correo y rol válidos son obligatorios.'}, status_code=400)
    if rol == 'padre' and not entrada.alumno_id:
        return JSONResponse({'error': 'Una cuenta de padre debe estar vinculada a un estudiante.'}, status_code=400)

    cargo = 'Docente / Tutor SIGE-360'
    if rol == 'padre':
        al = consultar("SELECT nombre_completo, grado, seccion FROM alumnos WHERE id = %s LIMIT 1", (entrada.alumno_id,))
        if not al:
            return JSONResponse({'error': 'Estudiante no encontrado.'}, status_code=404)
        cargo = f"Apoderado de {al[0]['nombre_completo']} ({al[0]['grado']} {al[0]['seccion']})"

    nueva_pwd = (entrada.password or '').strip()
    if nueva_pwd and len(nueva_pwd) < 4:
        return JSONResponse({'error': 'La nueva contraseña debe tener al menos 4 caracteres.'}, status_code=400)

    try:
        with obtener_conexion() as conn:
            with conn.cursor() as cur:
                if nueva_pwd:
                    cur.execute(
                        """UPDATE usuarios
                           SET email = %s, password = %s, rol = %s, nombre = %s, cargo = %s, alumno_id = %s
                           WHERE id = %s""",
                        (email, hashear_password(nueva_pwd), rol, entrada.nombre.strip(), cargo, entrada.alumno_id if rol == 'padre' else None, usuario_id),
                    )
                else:
                    cur.execute(
                        """UPDATE usuarios
                           SET email = %s, rol = %s, nombre = %s, cargo = %s, alumno_id = %s
                           WHERE id = %s""",
                        (email, rol, entrada.nombre.strip(), cargo, entrada.alumno_id if rol == 'padre' else None, usuario_id),
                    )
                if rol == 'padre' and entrada.alumno_id and entrada.telegram_chat_id is not None:
                    tg_limpio = entrada.telegram_chat_id.strip() or None
                    cur.execute(
                        "UPDATE alumnos SET telegram_chat_id = %s WHERE id = %s",
                        (tg_limpio, entrada.alumno_id),
                    )
            conn.commit()
        return {'ok': True, 'mensaje': f'Cuenta {email} actualizada correctamente en PostgreSQL.'}
    except Exception as exc:
        print('[APP] Error editando usuario:', exc)
        return JSONResponse({'error': 'No se pudo actualizar la cuenta (verifica que el correo no esté duplicado).'}, status_code=400)


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

    # Si no vino alumno_id explícito (ej. desde el botón del chat), detectar qué estudiante menciona el mensaje (sin importar tildes)
    def sin_tildes(s: str) -> str:
        return ''.join(c for c in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(c))

    alumno_id_resuelto = entrada.alumno_id
    if not alumno_id_resuelto:
        todos_al = consultar("SELECT id, codigo_estudiante, nombre_completo FROM alumnos")
        texto_norm = sin_tildes(texto)
        for al in todos_al:
            partes = sin_tildes(al['nombre_completo']).split()
            nombre_corto = ' '.join(partes[:2]) if len(partes) >= 2 else sin_tildes(al['nombre_completo'])
            if sin_tildes(al['codigo_estudiante']) in texto_norm or nombre_corto in texto_norm:
                alumno_id_resuelto = al['id']
                break

    # Si el alumno tiene su propio apoderado vinculado en PostgreSQL, usar ese chat_id
    if alumno_id_resuelto:
        filas_tg = consultar(
            "SELECT nombre_completo, telegram_chat_id FROM alumnos WHERE id = %s LIMIT 1",
            (alumno_id_resuelto,),
        )
        if filas_tg and filas_tg[0].get('telegram_chat_id'):
            chat_id_destino = str(filas_tg[0]['telegram_chat_id']).strip()
            origen_destino = f"apoderado vinculado de {filas_tg[0]['nombre_completo']}"

    enviado_externo = False
    detalle = 'Guardado en Portal de Padres (configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID en .env para envío al celular).'

    if token and chat_id_destino:
        try:
            payload_tg = {
                'chat_id': chat_id_destino,
                'text': (
                    f'🏫 SIGE-360 · Alerta al Apoderado\n\n'
                    f'{texto}\n\n'
                    f'👇 ¿Deseas consultar el historial de tu hijo/a o hacer una consulta? '
                    f'Toca un botón o escríbeme directamente aquí.'
                ),
            }
            if alumno_id_resuelto:
                payload_tg['reply_markup'] = _botones_alumno_telegram(alumno_id_resuelto, incluir_ack=True)
            r = requests.post(
                f'https://api.telegram.org/bot{token}/sendMessage',
                json=payload_tg,
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
                    (alumno_id_resuelto, texto[:1500], enviado_externo, detalle),
                )
            conn.commit()
    except Exception as exc:
        print('[APP] Error guardando alerta:', exc)

    return {'ok': True, 'enviado_telegram': enviado_externo, 'mensaje': detalle}


# ==================== BOT INTERACTIVO DE TELEGRAM (VINCULACIÓN + HISTORIAL + SIGE-BOT) ====================
def _botones_alumno_telegram(alumno_id: int, incluir_ack: bool = False):
    filas = [
        [
            {'text': '📊 Ver historial y notas', 'callback_data': f'hist:{alumno_id}'},
            {'text': '📅 Ver asistencia', 'callback_data': f'asis:{alumno_id}'},
        ]
    ]
    if incluir_ack:
        filas.append([{'text': '✅ Confirmar recibido', 'callback_data': f'ack:{alumno_id}'}])
    return {'inline_keyboard': filas}


def _buscar_alumno_por_chat_id(chat_id: str, alumno_id_preferido: int = None):
    """Devuelve el estudiante autorizado para un chat_id (Ley N.° 29733: solo su hijo vinculado o chat demo)."""
    chat_str = str(chat_id).strip()
    demo_chat = os.environ.get('TELEGRAM_CHAT_ID', '').strip()

    if alumno_id_preferido:
        filas = consultar(
            "SELECT id, codigo_estudiante, nombre_completo, grado, seccion, telegram_chat_id FROM alumnos WHERE id = %s LIMIT 1",
            (alumno_id_preferido,),
        )
        if filas:
            al = filas[0]
            tg_al = str(al.get('telegram_chat_id') or '').strip()
            if tg_al == chat_str or (demo_chat and chat_str == demo_chat):
                return al
        return None

    filas = consultar(
        "SELECT id, codigo_estudiante, nombre_completo, grado, seccion FROM alumnos WHERE telegram_chat_id = %s ORDER BY id ASC LIMIT 1",
        (chat_str,),
    )
    if filas:
        return filas[0]

    # Si es el chat demo (.env), usar el último estudiante sobre el que se envió alerta
    if demo_chat and chat_str == demo_chat:
        ult = consultar(
            """SELECT a.id, a.codigo_estudiante, a.nombre_completo, a.grado, a.seccion
               FROM alertas_enviadas alr
               JOIN alumnos a ON a.id = alr.alumno_id
               WHERE alr.alumno_id IS NOT NULL
               ORDER BY alr.id DESC LIMIT 1"""
        )
        if ult:
            return ult[0]
    return None


def _construir_resumen_historial_telegram(alumno_id: int) -> str:
    al_filas = consultar(
        "SELECT codigo_estudiante, nombre_completo, grado, seccion FROM alumnos WHERE id = %s LIMIT 1",
        (alumno_id,),
    )
    if not al_filas:
        return '⚠️ No se encontró el registro del estudiante.'
    al = al_filas[0]
    notas = consultar(
        """SELECT curso,
                  ROUND(AVG(nota)::numeric, 1) AS promedio,
                  MAX(bimestre) AS ult_bim,
                  COUNT(*) AS registros
           FROM notas
           WHERE alumno_id = %s
           GROUP BY curso
           ORDER BY promedio ASC, curso ASC""",
        (alumno_id,),
    )
    if not notas:
        return f"📘 {al['nombre_completo']} ({al['grado']} {al['seccion']})\nAún no registra calificaciones en el sistema."

    prom_general = sum(float(n['promedio']) for n in notas) / len(notas)
    lineas = [
        f"📘 Historial Académico — {al['nombre_completo']}",
        f"🎓 {al['grado']} {al['seccion']} · Código: {al['codigo_estudiante']}",
        f"⭐ Promedio general: {prom_general:.1f} / 20\n",
        "Resumen por curso:",
    ]
    for n in notas:
        p = float(n['promedio'])
        icono = '🔴' if p < 11 else ('🟡' if p < 14 else '🟢')
        lineas.append(f"{icono} {n['curso']}: {p:.1f} (hasta Bim. {n['ult_bim']})")

    lineas.append("\n💬 Puedes escribirme cualquier pregunta sobre el avance de tu hijo/a (ej. «¿en qué curso necesita refuerzo?»).")
    lineas.append("🔒 Información confidencial solo para el apoderado (Ley N.° 29733).")
    return '\n'.join(lineas)


def _construir_resumen_asistencia_telegram(alumno_id: int) -> str:
    al_filas = consultar(
        "SELECT codigo_estudiante, nombre_completo, grado, seccion FROM alumnos WHERE id = %s LIMIT 1",
        (alumno_id,),
    )
    if not al_filas:
        return '⚠️ No se encontró el registro del estudiante.'
    al = al_filas[0]
    conteo = consultar(
        """SELECT estado, COUNT(*) AS total
           FROM asistencia WHERE alumno_id = %s
           GROUP BY estado""",
        (alumno_id,),
    )
    tot = {r['estado']: int(r['total']) for r in conteo}
    recientes = consultar(
        """SELECT fecha, estado, hora_rfid
           FROM asistencia WHERE alumno_id = %s
           ORDER BY fecha DESC LIMIT 8""",
        (alumno_id,),
    )
    lineas = [
        f"📅 Control de Asistencia RFID — {al['nombre_completo']}",
        f"🎓 {al['grado']} {al['seccion']} · Código: {al['codigo_estudiante']}",
        f"✅ Presentes: {tot.get('PRESENTE', 0)} · 🟡 Tardanzas: {tot.get('TARDANZA', 0)} · 🔴 Faltas: {tot.get('FALTA', 0)}\n",
        "Últimos registros:",
    ]
    if not recientes:
        lineas.append("Sin registros recientes.")
    else:
        for r in recientes:
            est = r['estado']
            ico = '✅' if est == 'PRESENTE' else ('🟡' if est == 'TARDANZA' else '🔴')
            hora = f" ({r['hora_rfid']})" if r.get('hora_rfid') else ''
            lineas.append(f"{ico} {r['fecha']} — {est}{hora}")

    lineas.append("\n🔒 Información confidencial solo para el apoderado (Ley N.° 29733).")
    return '\n'.join(lineas)


def _formatear_html_telegram(texto: str) -> str:
    """Convierte texto limpio (o con **negritas**) a HTML seguro para Telegram."""
    seguro = html.escape(texto.strip())
    seguro = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', seguro)
    seguro = re.sub(r'^\s*[-*]\s+', '• ', seguro, flags=re.MULTILINE)
    return seguro


def _enviar_tg(token: str, chat_id, texto: str, reply_markup=None, es_html: bool = False):
    payload = {'chat_id': chat_id, 'text': texto[:4000]}
    if es_html:
        payload['parse_mode'] = 'HTML'
    if reply_markup:
        payload['reply_markup'] = reply_markup
    r = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json=payload,
        timeout=10,
    )
    if not r.ok and es_html:
        # Fallback a texto plano si Telegram rechaza alguna etiqueta
        payload.pop('parse_mode', None)
        payload['text'] = re.sub(r'<[^>]+>', '', texto)[:4000]
        requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json=payload, timeout=10)


def _consultar_agente_telegram(token: str, chat_id, al: dict, consulta_usuario: str):
    """Envía toda consulta del apoderado en Telegram al flujo completo n8n -> Gemini -> MCP -> PostgreSQL."""
    try:
        requests.post(
            f'https://api.telegram.org/bot{token}/sendChatAction',
            json={'chat_id': chat_id, 'action': 'typing'},
            timeout=5,
        )
    except Exception:
        pass

    mensaje_agente = (
        f"(Apoderado autenticado vía Telegram, solo autorizado para su hijo "
        f"{al['nombre_completo']} ID {al['id']}. "
        f"Formato obligatorio para Telegram móvil: responde de forma muy ordenada en secciones cortas con saltos de línea, "
        f"viñetas '•' y emojis sobrios como 📊, 📚, 📅, 💡. NO escribas un solo párrafo largo. "
        f"Cierra con una línea corta indicando que eres asistente de IA - Ley N.° 31814.) "
        f"{consulta_usuario}"
    )
    print(f"[TELEGRAM -> N8N/MCP] chat_id={chat_id} alumno_id={al['id']} consulta={consulta_usuario[:80]!r}")
    try:
        r_ia = requests.post(
            N8N_WEBHOOK_URL,
            json={'sesion': f'tg_{chat_id}', 'rol': 'padre', 'mensaje': mensaje_agente},
            timeout=60,
        )
        if r_ia.ok:
            resp_ia = (r_ia.json().get('respuesta') or '').strip()
        else:
            print(f'[TELEGRAM -> N8N/MCP] n8n respondió HTTP {r_ia.status_code}')
            resp_ia = ''
    except Exception as exc:
        print('[TELEGRAM -> N8N/MCP] Error conectando con n8n:', exc)
        resp_ia = ''

    if resp_ia:
        encabezado = (
            f"🤖 <b>SIGE-Bot · SIGE-360</b>\n"
            f"🎓 <i>{html.escape(al['nombre_completo'])} · {html.escape(al['grado'])} {html.escape(al['seccion'])}</i>\n"
            f"────────────────────\n\n"
        )
        cuerpo = _formatear_html_telegram(resp_ia)
        _enviar_tg(
            token,
            chat_id,
            f"{encabezado}{cuerpo}",
            reply_markup=_botones_alumno_telegram(al['id']),
            es_html=True,
        )
    else:
        _enviar_tg(
            token,
            chat_id,
            '⚠️ El asistente SIGE-Bot (n8n / Servidor MCP) no respondió en este momento. Verifica que n8n y el servidor MCP estén activos.',
            reply_markup=_botones_alumno_telegram(al['id']),
        )


def _bucle_vinculacion_telegram():
    """Escucha mensajes y botones en @SIGE360_Alertas_Bot: vinculación por código y consultas 100% vía n8n + MCP."""
    offset = 0
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
                timeout=12,
            ).json()
            for upd in resp.get('result', []):
                offset = upd['update_id'] + 1

                # 1. Botones interactivos (callback_query) -> pasan por n8n + MCP
                cb = upd.get('callback_query')
                if cb:
                    cb_id = cb.get('id')
                    data = (cb.get('data') or '').strip()
                    chat_id = (cb.get('message') or {}).get('chat', {}).get('id')
                    try:
                        requests.post(
                            f'https://api.telegram.org/bot{token}/answerCallbackQuery',
                            json={'callback_query_id': cb_id, 'text': 'Consultando a SIGE-Bot (MCP)...'},
                            timeout=6,
                        )
                    except Exception:
                        pass
                    if not chat_id or ':' not in data:
                        continue
                    accion, aid_str = data.split(':', 1)
                    try:
                        aid = int(aid_str)
                    except ValueError:
                        continue
                    al = _buscar_alumno_por_chat_id(str(chat_id), alumno_id_preferido=aid)
                    if not al:
                        _enviar_tg(
                            token,
                            chat_id,
                            '🔒 Por protección de datos (Ley N.° 29733), solo el apoderado vinculado puede consultar este historial.',
                        )
                        continue
                    if accion == 'hist':
                        _consultar_agente_telegram(
                            token,
                            chat_id,
                            al,
                            f"Consulta el historial académico y las notas por curso de mi hijo {al['nombre_completo']} (ID {al['id']}). "
                            f"Organiza la respuesta exactamente en 3 secciones con saltos de línea: "
                            f"1) 📊 Resumen general (promedio y situación), "
                            f"2) 📚 Notas por curso (una viñeta '•' por cada curso con su nota en línea aparte), "
                            f"3) 💡 Recomendaciones para casa (máximo 3 viñetas cortas).",
                        )
                    elif accion == 'asis':
                        _consultar_agente_telegram(
                            token,
                            chat_id,
                            al,
                            f"Consulta el historial de asistencia, tardanzas y faltas recientes de mi hijo {al['nombre_completo']} (ID {al['id']}). "
                            f"Organiza la respuesta exactamente en 3 secciones con saltos de línea: "
                            f"1) 📅 Resumen de asistencia (conteo de faltas y tardanzas), "
                            f"2) 🕒 Últimos registros RFID (una viñeta '•' por cada fecha en línea aparte), "
                            f"3) 💡 Acción recomendada para el apoderado.",
                        )
                    elif accion == 'ack':
                        try:
                            with obtener_conexion() as conn:
                                with conn.cursor() as cur:
                                    cur.execute(
                                        """INSERT INTO alertas_enviadas (alumno_id, canal, mensaje, enviado_externo, detalle_estado)
                                           VALUES (%s, 'TELEGRAM_ACK', %s, TRUE, 'Confirmado por apoderado desde Telegram')""",
                                        (al['id'], f"Apoderado (Telegram {chat_id}) confirmó lectura de alerta sobre {al['nombre_completo']}."),
                                    )
                                conn.commit()
                        except Exception as exc:
                            print('[TELEGRAM] Error guardando ACK:', exc)
                        _enviar_tg(
                            token,
                            chat_id,
                            f"✅ Confirmación registrada para {al['nombre_completo']}. El tutor ha sido notificado.\n\n"
                            f"Si deseas revisar sus notas o asistencia con SIGE-Bot, usa los botones o escríbeme tu pregunta.",
                            reply_markup=_botones_alumno_telegram(al['id']),
                        )
                    continue

                # 2. Mensajes de texto del apoderado -> pasan por n8n + MCP
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
                            f"Recibirás aquí las alertas tempranas de SIGE-360 y puedes consultar su historial cuando quieras:"
                        )
                        _enviar_tg(token, chat_id, respuesta_bot, reply_markup=_botones_alumno_telegram(al['id']))
                    else:
                        _enviar_tg(
                            token,
                            chat_id,
                            f"⚠️ No encontramos ningún estudiante con el código {codigo}. Verifica el código (ej. EST-2026-003).",
                        )
                    continue

                al_vinc = _buscar_alumno_por_chat_id(str(chat_id))
                if al_vinc:
                    t_low = ''.join(
                        c for c in unicodedata.normalize('NFKD', texto.lower()) if not unicodedata.combining(c)
                    ).strip()
                    if t_low in ('/start', '/help', 'hola', 'menu', 'buenos dias', 'buenas tardes', 'buenas noches'):
                        _enviar_tg(
                            token,
                            chat_id,
                            f"🏫 Hola, soy SIGE-Bot (asistente de IA de SIGE-360 conectado a n8n + MCP).\n"
                            f"Estudiante vinculado: {al_vinc['nombre_completo']} ({al_vinc['grado']} {al_vinc['seccion']}).\n\n"
                            f"Toca un botón o escríbeme cualquier consulta sobre sus notas o asistencia:",
                            reply_markup=_botones_alumno_telegram(al_vinc['id']),
                        )
                    elif t_low in ('si', 's', 'ok', 'claro', 'por favor'):
                        _consultar_agente_telegram(
                            token,
                            chat_id,
                            al_vinc,
                            f"Sí, quiero consultar el historial académico, notas y asistencia actual de mi hijo {al_vinc['nombre_completo']} (ID {al_vinc['id']}).",
                        )
                    else:
                        _consultar_agente_telegram(token, chat_id, al_vinc, texto)
                else:
                    respuesta_bot = (
                        "🏫 Bienvenido a SIGE-360 Alertas.\n"
                        "Para vincular tu celular con tu hijo/a, envíame su código de estudiante (ejemplo: EST-2026-003).\n"
                        "Por protección de datos (Ley N.° 29733), usamos códigos escolares simulados y no DNIs reales."
                    )
                    _enviar_tg(token, chat_id, respuesta_bot)
        except Exception as exc:
            print('[TELEGRAM] Error en bucle polling:', exc)
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


@app.get('/estudiantes.html')
def ruta_estudiantes(request: Request):
    return servir_pagina_docente(request, 'estudiantes.html')


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


@app.get('/semaforo.html')
def ruta_semaforo(request: Request):
    if not tiene_acceso_iot_o_tutor(request):
        return RedirectResponse('/login.html', status_code=302)
    return FileResponse(os.path.join(PUBLIC_DIR, 'semaforo.html'))


@app.get('/padres.html')
def servir_padres(request: Request):
    _, user = obtener_usuario_actual(request)
    if not user:
        return RedirectResponse('/login.html', status_code=302)
    return FileResponse(os.path.join(PUBLIC_DIR, 'padres.html'))


app.mount('/', StaticFiles(directory=PUBLIC_DIR), name='public')
