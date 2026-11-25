# app.py - Aplicación web SIGE-360 en Python (FastAPI + PostgreSQL + puente a n8n)
import os
import json
import uuid
from datetime import datetime
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
MCP_AUDIT_FILE = os.path.join(RAIZ, 'agente', 'mcp_audit.jsonl')

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


class RfidScanEntrada(BaseModel):
    alumno_id: int
    estado: str


class NotaEntrada(BaseModel):
    alumno_id: int
    curso: str
    bimestre: int
    nota: float


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


@app.get('/api/mcp-logs')
def api_mcp_logs():
    """Devuelve las últimas llamadas reales al servidor MCP (Rayos X del Agente)."""
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


@app.post('/api/rfid-scan')
def api_rfid_scan(entrada: RfidScanEntrada):
    """Registra una lectura simulada del lector RFID de puerta para cualquier alumno."""
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
def api_listar_notas():
    try:
        filas = consultar(
            """SELECT n.id, n.alumno_id, a.nombre_completo, a.grado, a.seccion,
                      n.curso, n.bimestre, n.nota, n.fecha_registro
               FROM notas n JOIN alumnos a ON a.id = n.alumno_id
               ORDER BY n.id DESC LIMIT 40"""
        )
        return {'notas': filas}
    except Exception as exc:
        print('[APP] Error listando notas:', exc)
        return JSONResponse({'error': 'No se pudieron cargar las notas'}, status_code=500)


@app.post('/api/notas')
def api_crear_nota(entrada: NotaEntrada):
    if entrada.nota < 0 or entrada.nota > 20 or entrada.bimestre not in (1, 2, 3, 4):
        return JSONResponse({'error': 'La nota debe estar entre 0 y 20, y el bimestre entre 1 y 4.'}, status_code=400)
    try:
        hoy = datetime.now().strftime('%Y-%m-%d')
        with obtener_conexion() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """INSERT INTO notas (alumno_id, curso, bimestre, nota, fecha_registro)
                       VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                    (entrada.alumno_id, entrada.curso.strip(), entrada.bimestre, round(entrada.nota, 2), hoy),
                )
                creado = cur.fetchone()
            conn.commit()
        return {'ok': True, 'id': creado['id'], 'mensaje': f'Nota {entrada.nota} en {entrada.curso} registrada y semáforo recalculado.'}
    except Exception as exc:
        print('[APP] Error registrando nota:', exc)
        return JSONResponse({'error': 'No se pudo registrar la nota'}, status_code=500)


@app.get('/api/convivencia')
def api_listar_convivencia():
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
def api_crear_incidencia(entrada: IncidenciaEntrada):
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
def api_crear_biblioteca(entrada: BibliotecaEntrada):
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
def api_crear_alumno(entrada: AlumnoEntrada):
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
def api_actualizar_intervencion(intervencion_id: int, entrada: IntervencionEstadoEntrada):
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
