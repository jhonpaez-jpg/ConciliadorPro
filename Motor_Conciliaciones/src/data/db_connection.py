"""
Capa de conexión unificada — soporta 3 motores sin cambiar nada más en el código.

Configuración via variable de entorno DATABASE_URL:

  SQLite  (local, sin internet):
      → No definir DATABASE_URL, o:
      DATABASE_URL=sqlite:///conciliacion.db

  MySQL   (PlanetScale, Aiven, Railway MySQL, etc.):
      DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname

  PostgreSQL (Railway, Supabase, Neon, etc.):
      DATABASE_URL=postgresql://user:password@host:5432/dbname

Solo cambia el .env — el resto del código no se toca.
"""

import os

# Cargar .env aquí — este módulo es el primero en leer DATABASE_URL
# y se importa en TODOS los procesos (reloader + worker de uvicorn)
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from sqlalchemy import create_engine, event
from sqlalchemy.pool import NullPool

# ── Resolver URL ──────────────────────────────────────────────────────────────
_raw_url = os.environ.get("DATABASE_URL", "sqlite:///conciliacion.db")

# Normalizar prefijos alternativos
if _raw_url.startswith("postgres://"):
    _raw_url = _raw_url.replace("postgres://", "postgresql://", 1)
if _raw_url.startswith("mysql://"):
    # Asegurar que usa pymysql como driver
    _raw_url = _raw_url.replace("mysql://", "mysql+pymysql://", 1)

IS_SQLITE = _raw_url.startswith("sqlite")
IS_MYSQL = _raw_url.startswith("mysql")
IS_POSTGRES = _raw_url.startswith("postgresql")

# ── Crear engine según el motor ───────────────────────────────────────────────
if IS_SQLITE:
    engine = create_engine(
        _raw_url,
        poolclass=NullPool,
        connect_args={"check_same_thread": False, "timeout": 30},
    )

    @event.listens_for(engine, "connect")
    def _set_wal(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA busy_timeout=30000")

elif IS_MYSQL:
    engine = create_engine(
        _raw_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 30},
    )

else:  # PostgreSQL
    engine = create_engine(
        _raw_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 30},
    )

print(
    f"🗄️  DB: {'SQLite' if IS_SQLITE else 'MySQL' if IS_MYSQL else 'PostgreSQL'} "
    f"— {_raw_url.split('@')[-1] if '@' in _raw_url else _raw_url}"
)


def get_connection():
    """Devuelve una conexión SQLAlchemy. Usar con 'with get_connection() as con:'"""
    return engine.connect()
