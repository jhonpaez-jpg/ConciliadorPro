import os

# ── Cargar .env PRIMERO — antes de cualquier import del proyecto ──────────────
# En Railway las vars vienen del panel, no del .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Importar DESPUÉS de cargar el .env para que DATABASE_URL ya esté disponible
from src.data.db_manager import DatabaseManager
from src.data.db_connection import IS_POSTGRES

# 1. Crear tablas PRIMERO — antes de arrancar el scheduler
db = DatabaseManager()
db.inicializar_tablas()
motor = "PostgreSQL (Railway)" if IS_POSTGRES else "SQLite (local)"
print(f"✅ Base de datos inicializada — {motor}")

# 2. Arrancar scheduler DESPUÉS de que las tablas existen
from src.api.routes import router, _scheduler_tick
from src.api.report_routes import report_router

_scheduler_tick()
print("✅ Scheduler de ejecuciones programadas iniciado.")

# 2. Definición única de la aplicación
app = FastAPI(
    title="Motor de Conciliación Bancaria 🚀",
    description="API para procesamiento de transacciones financieras",
    version="1.1.0",
)

# 3. Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Crear carpetas base si no existen
BASE_DIR = os.getcwd()
REPORT_DIR = os.path.join(BASE_DIR, "reportes")
os.makedirs(REPORT_DIR, exist_ok=True)

# 5. Inclusión de rutas del motor
app.include_router(router)
app.include_router(report_router)


# 6. Endpoint de salud
@app.get("/", tags=["General"])
async def root():
    return {"message": "API de Conciliación operando correctamente", "status": "online"}


# 7. Descarga de reportes
@app.get("/download-report/{file_name}", tags=["Reportes"])
async def download_report(file_name: str):
    file_path = os.path.join(REPORT_DIR, file_name)
    print(f"🔍 DEBUG: Intentando descargar: {file_path}")
    if os.path.exists(file_path):
        return FileResponse(
            path=file_path,
            filename=file_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    raise HTTPException(
        status_code=404, detail=f"El archivo {file_name} no existe en la carpeta de reportes."
    )


# 8. Endpoint para estado inicial del frontend
@app.get("/get-initial-data", tags=["General"])
async def get_initial_data():
    return {"status": "ready", "msg": "Conectado al servidor local"}
