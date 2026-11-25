# SIGE-360 — Sistema de Inteligencia Escolar Predictiva

Aplicación web en **Python (FastAPI + Uvicorn)** con base de datos **PostgreSQL**, servidor de herramientas **MCP en Python** (`mcp[cli]<2` / `FastMCP` sobre `streamable-http`) y agente conversacional orquestado en **n8n (Ruta A)** con **Google Gemini**.

## Arquitectura del proyecto

```text
Navegador (index.html + chat)
    │  POST /api/chat
    ▼
Backend Web en Python (app.py - FastAPI + sesiones)
    │  POST { sesion, rol, mensaje }
    ▼
Agente en n8n (Webhook → AI Agent + Gemini + Simple Memory → Respond to Webhook)
    │  MCP Client Tool (http://localhost:8000/mcp)
    ▼
Servidor MCP en Python (agente/servidor_mcp.py - 5 herramientas)
    │  Consultas SQL parametrizadas (%s) con privilegios mínimos
    ▼
Base de datos PostgreSQL (sige360 - datos 100% simulados)
```

## Estructura del repositorio

```text
├── app.py                                   # App web FastAPI + puente /api/chat + simulador RFID
├── requirements.txt                         # Librerías Python ("mcp[cli]<2", psycopg2-binary, fastapi, uvicorn...)
├── public/
│   ├── index.html                           # Panel principal SIGE-360 + chat integrado
│   ├── semaforo.html                        # Pantalla IoT Sala de Profesores (auto-refresco 4s)
│   ├── app.js                               # Lógica del dashboard y chat seguro (textContent)
│   ├── semaforo.js                          # Lógica de pantalla semáforo en vivo
│   └── styles.css                           # Estilos de la aplicación y pantalla IoT
├── agente/
│   ├── servidor_mcp.py                      # Servidor MCP FastMCP en http://localhost:8000/mcp
│   ├── instrucciones.txt                    # System prompt del agente SIGE-Bot
│   └── n8n_workflow_sige360.json            # Flujo de n8n listo para importar (Ruta A)
├── database/
│   ├── sige360_postgres.sql                 # Esquema PostgreSQL + 20 alumnos y datos simulados
│   └── crear_usuario_agente_postgres.sql    # Usuario PostgreSQL con SELECT + INSERT solo en intervenciones
├── docs/
│   ├── ficha_agente.md                      # Ficha del agente (1 página)
│   ├── casos_de_prueba.md                   # Tabla de 10 casos de prueba verificados
│   └── guion_demo_3min.md                   # Guion cronometrado de demostración
├── .env.example                             # Plantilla de variables (NO contiene claves)
└── .gitignore                               # Excluye .env, __pycache__ y .venv
```

## Requisitos previos

1. **Python 3.10 o superior** (instalado Python 3.12).
2. **PostgreSQL 14+** (PostgreSQL 18).
3. **n8n local** (`npx n8n`, en `http://localhost:5678`).
4. **Clave de API de Gemini** (Google AI Studio), configurada solo dentro de las credenciales de n8n.

---

## Instalación paso a paso

### 1. Crear la base de datos en PostgreSQL
1. Crea la base de datos `sige360` (`UTF8`) en pgAdmin o `psql`.
2. Ejecuta `database/sige360_postgres.sql`.
3. Ejecuta `database/crear_usuario_agente_postgres.sql`.

### 2. Instalar librerías de Python y configurar `.env`
```bash
pip install -r requirements.txt
```
Copia `.env.example` como `.env` y coloca tus credenciales locales de PostgreSQL y la URL de producción del Webhook de n8n:
```env
PORT=3060
MCP_PORT=8000
PGHOST=localhost
PGPORT=5432
PGDATABASE=sige360
PGUSER=postgres
PGPASSWORD=TU_PASSWORD_POSTGRES
MCP_PGUSER=agente_sige
MCP_PGPASSWORD=clave_sige360_segura
N8N_WEBHOOK_URL=http://localhost:5678/webhook/agente
```
> **Seguridad:** `.env` está en `.gitignore` y **nunca** se sube a GitHub.

### 3. Configurar el agente en n8n (Ruta A)
1. Abre n8n (`http://localhost:5678`) e importa `agente/n8n_workflow_sige360.json`.
2. En **Google Gemini Chat Model**, vincula tu API key de Gemini y selecciona **`Gemini Flash-Lite Latest`** (`models/gemini-flash-lite-latest`) o **`Gemini 3.8 Flash`**.
3. En **MCP Client Tool**, confirma la dirección `http://localhost:8000/mcp` (transporte **HTTP Streamable**).
4. **Publica / Activa** el flujo.

---

## Orden de encendido para probar y presentar en la feria

1. **PostgreSQL** encendido (puerto `5432`).
2. **Servidor MCP en Python** (Terminal 1):
   ```bash
   python agente/servidor_mcp.py
   ```
   Queda activo en `http://localhost:8000/mcp`.
3. **n8n** encendido con el flujo **Publicado / Activo** (`http://localhost:5678`).
4. **Aplicación web SIGE-360 en Python** (Terminal 2):
   ```bash
   uvicorn app:app --port 3060
   ```
   *(Sin `--reload` en Windows).* Abre `http://localhost:3060` y `http://localhost:3060/semaforo.html`.

## Seguridad y uso responsable
- **Sin claves en GitHub:** `.env` excluido en `.gitignore`; la API key de Gemini vive solo en n8n.
- **Privilegios mínimos:** `agente_sige` solo tiene `SELECT` en todas las tablas e `INSERT` únicamente en `intervenciones_tutoriales` (sin `UPDATE` ni `DELETE`).
- **Confirmación explícita:** `registrar_intervencion_tutorial` exige `confirmado=True` tras confirmar con el tutor.
- **Datos 100% simulados (Ley N.° 29733)** y **transparencia IA (Ley N.° 31814)**.
