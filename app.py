# app.py - Aplicación web SIGE-360 en Python (FastAPI + PostgreSQL + puente a n8n)
import os
import uuid
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

RAIZ = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(RAIZ, '.env'))

N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', 'http://localhost:5678/webhook/agente')
PORT = int(os.environ.get('PORT', '3060'))

# Sesiones en memoria (id_sesion -> rol)
SESIONES: dict[str, str] = {}

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


def obtener_o_crear_sesion(request: Request, response: Response) -> tuple[str, str]:
    sid = request.cookies.get('sige360_sid')
    if not sid:
        sid = uuid.uuid4().hex
        response.set_cookie('sige360_sid', sid, httponly=True, max_age=14400)
    rol = SESIONES.setdefault(sid, 'tutor')
    return sid, rol


class RolEntrada(BaseModel):
    rol: str


class ChatEntrada(BaseModel):
    mensaje: str


@app.get('/api/sesion')
def api_sesion(request: Request, response: Response):
    sid, rol = obtener_o_crear_sesion(request, response)
    return {'sesion': sid, 'rol': rol}


@app.post('/api/rol')
def api_rol(entrada: RolEntrada, request: Request, response: Response):
    if entrada.rol not in ('tutor', 'padre'):
        return JSONResponse({'error': 'Rol inválido'}, status_code=400)
    sid, _ = obtener_o_crear_sesion(request, response)
    SESIONES[sid] = entrada.rol
    return {'ok': True, 'rol': entrada.rol}


@app.get('/api/dashboard')
def api_dashboard():
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
def api_alumno_detalle(alumno_id: int):
    try:
        filas = consultar(f"{SQL_METRICAS} WHERE a.id = %s LIMIT 1", (alumno_id,))
        if not filas:
            return JSONResponse({'error': 'Alumno no encontrado'}, status_code=404)
        perfil = evaluar_fila(filas[0])
        notas = consultar(
            "SELECT curso, bimestre, nota, fecha_registro FROM notas WHERE alumno_id = %s ORDER BY fecha_registro DESC LIMIT 10",
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


@app.post('/api/simular-rfid')
def api_simular_rfid():
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
def api_reset_demo():
    alumno_id = 3
    with obtener_conexion() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM asistencia WHERE alumno_id = %s AND fecha >= '2026-11-23'", (alumno_id,))
            cur.execute("DELETE FROM notas WHERE alumno_id = %s AND fecha_registro >= '2026-11-23'", (alumno_id,))
        conn.commit()
    return {'ok': True, 'mensaje': 'Demo reiniciada: Lucas Mendoza volvió a su estado base (ÁMBAR).'}


@app.post('/api/chat')
def api_chat(entrada: ChatEntrada, request: Request, response: Response):
    sid, rol = obtener_o_crear_sesion(request, response)
    mensaje = entrada.mensaje.strip()
    if not mensaje or len(mensaje) > 500:
        return {'respuesta': 'Escriba una consulta de hasta 500 caracteres.'}

    try:
        r = requests.post(
            N8N_WEBHOOK_URL,
            json={'sesion': sid, 'rol': rol, 'mensaje': mensaje},
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


# Servir archivos estáticos del frontend
PUBLIC_DIR = os.path.join(RAIZ, 'public')


@app.get('/')
def servir_inicio():
    return FileResponse(os.path.join(PUBLIC_DIR, 'index.html'))


app.mount('/', StaticFiles(directory=PUBLIC_DIR), name='public')
