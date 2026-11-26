# servidor_mcp.py - Herramientas MCP de SIGE-360 sobre PostgreSQL (Ruta A: n8n)
import os
import json
import time
import logging
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


class _SilenciarCierreSSE(logging.Filter):
    """Oculta el ClosedResourceError cosmético que emite mcp 1.x cuando n8n cierra la sesión (DELETE /mcp 200 OK)."""

    def filter(self, record: logging.LogRecord) -> bool:
        if 'Error in standalone SSE writer' in record.getMessage():
            if record.exc_info and record.exc_info[0] and record.exc_info[0].__name__ == 'ClosedResourceError':
                return False
        return True


logging.getLogger('mcp.server.streamable_http').addFilter(_SilenciarCierreSSE())

# Carga variables desde .env en la raíz del proyecto
RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(RAIZ, '.env'))
AUDIT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mcp_audit.jsonl')

mcp = FastMCP('sige360-herramientas')


def registrar_auditoria_mcp(herramienta: str, parametros: dict, resumen: str, inicio: float):
    """Guarda un rastro ligero local para el panel Rayos X MCP en tiempo real."""
    try:
        ms = int((time.perf_counter() - inicio) * 1000)
        print(f"[MCP -> RESULTADO] {herramienta} => {resumen} ({ms} ms)", flush=True)
        evento = {
            'hora': datetime.now().strftime('%H:%M:%S'),
            'herramienta': herramienta,
            'parametros': parametros,
            'resumen': resumen,
            'ms': ms,
        }
        with open(AUDIT_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(evento, ensure_ascii=False) + '\n')
    except Exception:
        pass


def obtener_conexion():
    return psycopg2.connect(
        host=os.environ.get('PGHOST', 'localhost'),
        port=int(os.environ.get('PGPORT', '5432')),
        dbname=os.environ.get('PGDATABASE', 'sige360'),
        user=os.environ.get('MCP_PGUSER', 'agente_sige'),
        password=os.environ.get('MCP_PGPASSWORD', ''),
    )


def consultar(sql: str, parametros: tuple = ()) -> list[dict]:
    """Ejecuta una consulta SELECT parametrizada y devuelve una lista de diccionarios."""
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

    if score >= 60:
        nivel = 'ROJO'
    elif score >= 30:
        nivel = 'AMBAR'
    else:
        nivel = 'VERDE'

    return {
        'alumno_id': m['alumno_id'],
        'codigo_estudiante': m['codigo_estudiante'],
        'nombre_completo': m['nombre_completo'],
        'grado': f"{m['grado']} {m['seccion']}",
        'apoderado_nombre': m['apoderado_nombre'],
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


@mcp.tool()
def calcular_indice_riesgo(alumno_id: int) -> dict:
    """Calcula el índice de riesgo de deserción (0 a 100), nivel de semáforo (ROJO, AMBAR o VERDE)
    y desglose por asistencia, notas, convivencia y biblioteca para un alumno específico.
    Usar cuando pregunten por el riesgo, semáforo o alerta de un estudiante por su ID."""
    t0 = time.perf_counter()
    print(f"[MCP] calcular_indice_riesgo(alumno_id={alumno_id})")
    filas = consultar(f"{SQL_METRICAS} WHERE a.id = %s LIMIT 1", (alumno_id,))
    if not filas:
        registrar_auditoria_mcp('calcular_indice_riesgo', {'alumno_id': alumno_id}, 'No encontrado', t0)
        return {'encontrado': False, 'mensaje': f'No existe ningún alumno con ID {alumno_id}.'}
    res = {'encontrado': True, **evaluar_fila(filas[0])}
    registrar_auditoria_mcp('calcular_indice_riesgo', {'alumno_id': alumno_id}, f"{res['nombre_completo']} → {res['indice_riesgo']} ({res['nivel_semaforo']})", t0)
    return res


@mcp.tool()
def listar_alumnos_en_riesgo(nivel: str = 'ROJO', rol_usuario: str = 'tutor') -> dict:
    """Lista los estudiantes ordenados de mayor a menor índice de riesgo escolar.
    Permite filtrar por nivel: ROJO, AMBAR, VERDE o TODOS. Solo para rol tutor.
    Usar cuando pregunten qué alumnos están en riesgo, en alerta roja o necesitan atención urgente."""
    t0 = time.perf_counter()
    print(f"[MCP] listar_alumnos_en_riesgo(nivel={nivel}, rol={rol_usuario})")
    if rol_usuario.lower() == 'padre':
        registrar_auditoria_mcp('listar_alumnos_en_riesgo', {'nivel': nivel, 'rol': rol_usuario}, 'Acceso denegado (PROT-10)', t0)
        return {
            'autorizado': False,
            'mensaje': 'Por política de privacidad (PROT-10 / Ley 29733), un padre o apoderado no puede ver el listado global de alumnos en riesgo. Solo puede consultar el resumen de su propio hijo.',
        }
    filas = consultar(f"{SQL_METRICAS} ORDER BY a.id ASC LIMIT 120")
    evaluados = [evaluar_fila(f) for f in filas]
    evaluados.sort(key=lambda x: (-x['indice_riesgo'], x['alumno_id']))
    nivel_norm = nivel.upper().strip()
    if nivel_norm in ('ROJO', 'AMBAR', 'VERDE'):
        evaluados = [x for x in evaluados if x['nivel_semaforo'] == nivel_norm]
    resumen = [
        {
            'alumno_id': x['alumno_id'],
            'codigo_estudiante': x['codigo_estudiante'],
            'nombre_completo': x['nombre_completo'],
            'grado': x['grado'],
            'indice_riesgo': x['indice_riesgo'],
            'nivel_semaforo': x['nivel_semaforo'],
            'promedio_notas': x['metricas']['promedio_notas'],
            'faltas': x['metricas']['faltas'],
        }
        for x in evaluados[:15]
    ]
    registrar_auditoria_mcp('listar_alumnos_en_riesgo', {'nivel': nivel_norm}, f"{len(resumen)} estudiantes devueltos", t0)
    return {'total': len(resumen), 'nivel_consultado': nivel_norm, 'alumnos': resumen}


@mcp.tool()
def consultar_historial_academico(busqueda: str, rol_usuario: str = 'tutor') -> dict:
    """Busca un alumno por nombre, apellido o código (ej. Mateo, Lucas, EST-2026-003) y devuelve
    su perfil, notas por curso, faltas recientes, incidencias de convivencia, biblioteca e
    intervenciones tutoriales. Usar cuando pregunten por datos, notas, faltas o historial de un alumno."""
    t0 = time.perf_counter()
    print(f"[MCP] consultar_historial_academico(busqueda={busqueda}, rol={rol_usuario})")
    patron = f"%{busqueda.strip()}%"
    alumnos = consultar(
        """SELECT id, codigo_estudiante, nombre_completo, grado, seccion, apoderado_nombre
           FROM alumnos WHERE nombre_completo ILIKE %s OR codigo_estudiante ILIKE %s LIMIT 5""",
        (patron, patron),
    )
    if not alumnos:
        registrar_auditoria_mcp('consultar_historial_academico', {'busqueda': busqueda}, 'Sin coincidencias', t0)
        return {'encontrado': False, 'mensaje': f'No se encontró ningún alumno que coincida con "{busqueda}".'}

    alumno = alumnos[0]
    aid = alumno['id']
    riesgo = calcular_indice_riesgo(aid)
    notas = consultar(
        "SELECT curso, bimestre, nota, fecha_registro FROM notas WHERE alumno_id = %s ORDER BY fecha_registro DESC LIMIT 10",
        (aid,),
    )
    asistencia = consultar(
        "SELECT fecha, estado, hora_rfid, origen FROM asistencia WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 10",
        (aid,),
    )

    if rol_usuario.lower() == 'padre':
        registrar_auditoria_mcp('consultar_historial_academico', {'busqueda': busqueda, 'rol': 'padre'}, f"Resumen seguro: {alumno['nombre_completo']}", t0)
        return {
            'encontrado': True,
            'modo': 'resumen_apoderado',
            'alumno': {'alumno_id': aid, 'nombre_completo': alumno['nombre_completo'], 'grado': f"{alumno['grado']} {alumno['seccion']}"},
            'promedio_notas': riesgo['metricas']['promedio_notas'],
            'faltas_recientes': riesgo['metricas']['faltas'],
            'notas': notas,
            'asistencia': asistencia,
            'nota_privacidad': 'Se omiten incidencias internas y datos de otros estudiantes según protocolo PROT-10.',
        }

    incidencias = consultar(
        "SELECT fecha, tipo, gravedad, descripcion FROM incidencias_convivencia WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 5",
        (aid,),
    )
    biblioteca = consultar(
        "SELECT fecha, accion, libro FROM biblioteca_uso WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 5",
        (aid,),
    )
    intervenciones = consultar(
        "SELECT id, fecha, tutor_nombre, motivo, accion_acordada, estado FROM intervenciones_tutoriales WHERE alumno_id = %s ORDER BY fecha DESC LIMIT 5",
        (aid,),
    )
    registrar_auditoria_mcp('consultar_historial_academico', {'busqueda': busqueda}, f"Perfil completo: {alumno['nombre_completo']}", t0)
    return {
        'encontrado': True,
        'alumno': alumno,
        'riesgo': riesgo,
        'notas': notas,
        'asistencia': asistencia,
        'incidencias_convivencia': incidencias,
        'biblioteca': biblioteca,
        'intervenciones_tutoriales': intervenciones,
    }


@mcp.tool()
def listar_notas_bajas(nota_maxima: float = 11.0, curso: str = '', rol_usuario: str = 'tutor') -> dict:
    """Lista los estudiantes con notas desaprobatorias o menores a una nota máxima indicada (por defecto 11)
    mostrando en qué curso y bimestre tienen esa nota baja. Opcionalmente filtra por nombre de curso.
    Usar cuando pregunten qué alumnos tienen notas o promedios menores a un número, desaprobados o jalados por curso."""
    t0 = time.perf_counter()
    print(f"[MCP] listar_notas_bajas(nota_maxima={nota_maxima}, curso={curso}, rol={rol_usuario})")
    if rol_usuario.lower() == 'padre':
        registrar_auditoria_mcp('listar_notas_bajas', {'nota_maxima': nota_maxima, 'rol': rol_usuario}, 'Acceso denegado (PROT-10)', t0)
        return {
            'autorizado': False,
            'mensaje': 'Por política de privacidad (PROT-10 / Ley 29733), un padre no puede ver el listado de notas bajas de otros estudiantes.',
        }
    curso_limpio = curso.strip()
    if curso_limpio:
        filas = consultar(
            """SELECT a.id AS alumno_id, a.nombre_completo, a.grado, a.seccion,
                      n.curso, n.bimestre, n.nota,
                      (SELECT ROUND(AVG(n2.nota)::numeric, 2) FROM notas n2 WHERE n2.alumno_id = a.id) AS promedio_general
               FROM notas n JOIN alumnos a ON a.id = n.alumno_id
               WHERE n.nota < %s AND n.curso ILIKE %s
               ORDER BY n.nota ASC, a.nombre_completo ASC LIMIT 20""",
            (nota_maxima, f'%{curso_limpio}%'),
        )
    else:
        filas = consultar(
            """SELECT a.id AS alumno_id, a.nombre_completo, a.grado, a.seccion,
                      n.curso, n.bimestre, n.nota,
                      (SELECT ROUND(AVG(n2.nota)::numeric, 2) FROM notas n2 WHERE n2.alumno_id = a.id) AS promedio_general
               FROM notas n JOIN alumnos a ON a.id = n.alumno_id
               WHERE n.nota < %s
               ORDER BY n.nota ASC, a.nombre_completo ASC LIMIT 20""",
            (nota_maxima,),
        )
    registrar_auditoria_mcp('listar_notas_bajas', {'nota_maxima': nota_maxima, 'curso': curso_limpio or 'TODOS'}, f"{len(filas)} registros < {nota_maxima}", t0)
    if not filas:
        return {'encontrado': False, 'mensaje': f'No hay estudiantes con notas menores a {nota_maxima}.'}
    return {'encontrado': True, 'umbral': nota_maxima, 'total': len(filas), 'registros': filas}


@mcp.tool()
def consultar_protocolo_tutoria(tema: str) -> dict:
    """Busca en el reglamento interno, protocolos de tutoría y guías de alerta temprana del MINEDU
    según un tema o palabra clave (ej. '3 faltas', 'alerta roja', 'aislamiento', 'mensaje apoderado').
    Usar cuando pregunten qué dice el protocolo, reglamento o guía MINEDU."""
    t0 = time.perf_counter()
    print(f"[MCP] consultar_protocolo_tutoria(tema={tema})")
    patron = f"%{tema.strip()}%"
    filas = consultar(
        """SELECT codigo, categoria, titulo, nivel_riesgo, contenido
           FROM protocolos_minedu
           WHERE titulo ILIKE %s OR categoria ILIKE %s OR contenido ILIKE %s OR nivel_riesgo ILIKE %s
           LIMIT 4""",
        (patron, patron, patron, patron),
    )
    if not filas:
        registrar_auditoria_mcp('consultar_protocolo_tutoria', {'tema': tema}, 'Sin protocolos', t0)
        return {'encontrado': False, 'mensaje': f'No se hallaron protocolos sobre "{tema}".'}
    codigos = ', '.join(f['codigo'] for f in filas)
    registrar_auditoria_mcp('consultar_protocolo_tutoria', {'tema': tema}, f"Protocolos RAG: {codigos}", t0)
    return {'encontrado': True, 'protocolos': filas}


@mcp.tool()
def registrar_intervencion_tutorial(
    alumno_id: int,
    motivo: str,
    accion_acordada: str,
    rol_usuario: str = 'tutor',
    confirmado: bool = False,
) -> dict:
    """Registra una nueva intervención tutorial para un alumno en PostgreSQL.
    SOLO permitido para rol 'tutor' y SIEMPRE requiere confirmación previa (confirmado=False primero,
    y confirmado=True solo después de que el tutor confirme). Nunca borra ni modifica registros."""
    t0 = time.perf_counter()
    print(f"[MCP] registrar_intervencion_tutorial(alumno_id={alumno_id}, rol={rol_usuario}, confirmado={confirmado})")
    if rol_usuario.lower() != 'tutor':
        registrar_auditoria_mcp('registrar_intervencion_tutorial', {'alumno_id': alumno_id, 'rol': rol_usuario}, 'Escritura denegada (rol padre)', t0)
        return {
            'registrado': False,
            'autorizado': False,
            'mensaje': 'Acción denegada: solo el tutor o docente puede registrar intervenciones. Los padres solo tienen lectura.',
        }
    alumnos = consultar("SELECT id, nombre_completo FROM alumnos WHERE id = %s LIMIT 1", (alumno_id,))
    if not alumnos:
        return {'registrado': False, 'mensaje': f'No existe alumno con ID {alumno_id}.'}

    if not confirmado:
        registrar_auditoria_mcp('registrar_intervencion_tutorial', {'alumno_id': alumno_id, 'confirmado': False}, 'Esperando confirmación del tutor', t0)
        return {
            'registrado': False,
            'requiere_confirmacion': True,
            'resumen_pendiente': {
                'alumno': alumnos[0]['nombre_completo'],
                'motivo': motivo,
                'accion_acordada': accion_acordada,
            },
            'mensaje': 'Muestra este resumen y pide confirmación explícita al tutor antes de llamar nuevamente con confirmado=True.',
        }

    with obtener_conexion() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """INSERT INTO intervenciones_tutoriales (alumno_id, tutor_nombre, motivo, accion_acordada, estado)
                   VALUES (%s, 'Tutor SIGE-360', %s, %s, 'PROGRAMADA')
                   RETURNING id, estado""",
                (alumno_id, motivo, accion_acordada),
            )
            creado = dict(cur.fetchone())
        conn.commit()

    registrar_auditoria_mcp('registrar_intervencion_tutorial', {'alumno_id': alumno_id, 'confirmado': True}, f"INSERT intervención #{creado['id']}", t0)
    return {
        'registrado': True,
        'intervencion_id': creado['id'],
        'alumno': alumnos[0]['nombre_completo'],
        'estado': creado['estado'],
        'mensaje': 'Intervención tutorial registrada correctamente en PostgreSQL.',
    }


if __name__ == '__main__':
    # Ruta A (n8n): servidor MCP en modo web http://localhost:8000/mcp
    mcp.run(transport='streamable-http')
