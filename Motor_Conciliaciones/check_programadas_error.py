from dotenv import load_dotenv
load_dotenv('.env')
from src.data.db_connection import engine
from sqlalchemy import text
import os

with engine.connect() as con:
    rows = con.execute(text(
        "SELECT id, archivo_nombre, archivo_path, estado, ejecutado_en "
        "FROM ejecucion_programada WHERE estado = 'ERROR' ORDER BY id DESC LIMIT 5"
    )).fetchall()
    print(f"Programadas con ERROR: {len(rows)}")
    for r in rows:
        print(f"  id={r[0]} archivo={r[1]}")
        print(f"    path={r[2]}")
        print(f"    ejecutado={r[4]}")
        existe = os.path.exists(r[2]) if r[2] else False
        print(f"    archivo existe: {existe}")
        if not existe and r[2]:
            # Intentar con _BASE_DIR
            from src.api.routes import _BASE_DIR
            ruta_abs = os.path.join(_BASE_DIR, r[2]) if not os.path.isabs(r[2]) else r[2]
            print(f"    ruta absoluta: {ruta_abs}")
            print(f"    existe con BASE_DIR: {os.path.exists(ruta_abs)}")
