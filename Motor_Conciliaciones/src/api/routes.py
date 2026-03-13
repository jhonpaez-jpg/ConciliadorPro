from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Literal
import shutil, os, gc, sqlite3, time
from collections import defaultdict

from src.data.ingestor import DataIngestor
from src.data.db_manager import DatabaseManager
from src.core.engine import ReconciliationEngine
from src.core.models import Transaccion
from src.utils.reporter import ReconciliationReporter

router   = APIRouter()
db       = DatabaseManager("conciliacion.db")
reporter = ReconciliationReporter()

BATCH_SIZE = 50_000

# Estado persistido en disco (compartido entre workers)
_ESTADO_FILE = "estado_proceso.json"

def _leer_estado() -> dict:
    try:
        import json
        with open(_ESTADO_FILE, "r") as f:
            return json.load(f)
    except:
        return {"fase": "idle", "mensaje": "", "conciliados": 0,
                "pendientes": 0, "tasa": 0.0, "reporte": None}

def _escribir_estado(estado: dict):
    import json
    with open(_ESTADO_FILE, "w") as f:
        json.dump(estado, f)

# Inicializar si no existe
if not os.path.exists(_ESTADO_FILE):
    _escribir_estado({"fase": "idle", "mensaje": "", "conciliados": 0,
                      "pendientes": 0, "tasa": 0.0, "reporte": None})


def filas_a_transacciones(filas_db):
    return [
        Transaccion(
            id_transaccion  = f[0],
            descripcion     = f[1],
            cuenta_contable = f[2],
            monto_centavos  = f[3],
            n_diario        = f[4],
            localidad       = str(f[5]),
            periodo         = str(f[6]),
            tipo            = str(f[7]),
            id_lote         = f[8],
        )
        for f in filas_db
    ]


# ══════════════════════════════════════════════════════════════════
# TAREA BACKGROUND — carga + motor + F5
# ══════════════════════════════════════════════════════════════════
def _procesar_en_background(temp_path: str, id_lote: int):
    try:
        # ── 1. Ingestar ──────────────────────────────────────────
        _escribir_estado({**_leer_estado(), "fase": "cargando", "mensaje": "Leyendo Excel y filtrando SIF82/TES82..."})
        t0 = time.time()

        ingestor = DataIngestor(temp_path)
        df_limpio = ingestor.procesar_excel()
        cuenta = str(df_limpio["cuenta_contable"][0])
        total_leido = len(df_limpio)
        print(f"📥 {total_leido:,} regs leídos en {time.time()-t0:.1f}s")

        # ── 2. Insertar en DB por lotes ──────────────────────────
        _escribir_estado({**_leer_estado(), "mensaje": f"Insertando {total_leido:,} registros en DB..."})
        db.limpiar_transacciones_lote(id_lote)
        registros = [
            (r["descripcion"], str(r["cuenta_contable"]), r["monto_centavos"],
             r["n_diario"], str(r["localidad"]), str(r["periodo"]), str(r["tipo"]), id_lote)
            for r in df_limpio.to_dicts()
        ]
        del df_limpio; gc.collect()

        for i in range(0, len(registros), BATCH_SIZE):
            db.insertar_transacciones(registros[i:i+BATCH_SIZE])
        del registros; gc.collect()
        print(f"💾 DB cargada en {time.time()-t0:.1f}s")

        # ── 3. Motor por localidades (F1-F4) ─────────────────────
        _escribir_estado({**_leer_estado(), "fase": "procesando", "mensaje": "Ejecutando motor por localidades..."})
        localidades = db.obtener_localidades_unicas_por_lote(cuenta, id_lote)
        total_c = 0

        for idx, localidad in enumerate(localidades, 1):
            filas_db = db.obtener_pendientes_por_localidad(cuenta, localidad, id_lote)
            if not filas_db: continue
            txs = filas_a_transacciones(filas_db)
            del filas_db; gc.collect()

            _escribir_estado({**_leer_estado(), "mensaje": f"[{idx}/{len(localidades)}] Localidad {localidad}: {len(txs):,} regs"})
            engine = ReconciliationEngine()
            conciliadas, _ = engine.ejecutar_proceso_completo(txs)
            del txs; gc.collect()

            if conciliadas:
                # conciliadas = list[{"fase": "F1"|..., "grupo": [...]}]
                from collections import defaultdict as _dd2
                por_fase = _dd2(list)
                for entry in conciliadas:
                    por_fase[entry["fase"]].append(entry["grupo"])
                for fase_label, grupos in por_fase.items():
                    if grupos:
                        db.registrar_conciliacion_masiva(grupos, fase_origen=fase_label)
                total_c += sum(len(entry["grupo"]) for entry in conciliadas)
            del conciliadas, engine; gc.collect()

        print(f"✅ Motor localidades: {total_c:,} conciliados")

        # ── 4. F5 — monto puro en SQLite ─────────────────────────
        _escribir_estado({**_leer_estado(), "mensaje": "F5: Conciliando por monto puro..."})
        f5 = db.conciliar_por_monto_puro(cuenta, id_lote)
        total_c += f5
        print(f"✅ F5: {f5:,} conciliados por monto puro")

        # ── 5. Reporte desde DB ───────────────────────────────────
        _escribir_estado({**_leer_estado(), "mensaje": "Generando reporte..."})
        ruta = reporter.generar_excel_desde_db(db, cuenta, id_lote)

        pendientes_db = db.contar_pendientes_lote(cuenta, id_lote)
        tasa = (total_c / total_leido * 100) if total_leido else 0

        # Obtener período del lote
        periodos = db.obtener_periodos_disponibles(cuenta, id_lote)
        periodo_str = periodos[0] if periodos else None

        _escribir_estado({
            "fase": "listo",
            "mensaje": f"Completado en {time.time()-t0:.0f}s",
            "conciliados": total_c,
            "pendientes": pendientes_db,
            "tasa": round(tasa, 2),
            "reporte": ruta,
            "cuenta": cuenta,
            "total_leido": total_leido,
            "periodo": periodo_str,
        })
        print(f"🏁 Todo listo: {total_c:,} conciliados ({tasa:.1f}%) en {time.time()-t0:.0f}s")

    except Exception as e:
        import traceback
        _escribir_estado({**_leer_estado(), "fase": "error", "mensaje": str(e)})
        print(f"❌ Error background: {e}")
        traceback.print_exc()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Subir archivo (responde inmediato, procesa en background)
# ══════════════════════════════════════════════════════════════════
@router.post("/upload-and-reconcile/", tags=["Conciliación"])
async def upload_and_reconcile(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    modo: Literal["un_periodo", "multi_periodo"] = Query(default="un_periodo")
):
    """
    Sube el archivo y lanza el proceso en background.
    Responde inmediatamente con status 202.
    Consulta /estado/ para ver el progreso.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx o .xls")

    estado_actual = _leer_estado()
    if estado_actual["fase"] in ("cargando", "procesando"):
        raise HTTPException(409, "Ya hay un proceso en curso. Consulta /estado/")

    os.makedirs("data_samples", exist_ok=True)
    temp_path = f"data_samples/temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    id_lote = 1 if modo == "un_periodo" else 2
    _escribir_estado({"fase": "iniciando", "mensaje": "Archivo recibido, iniciando...",
               "conciliados": 0, "pendientes": 0, "tasa": 0.0, "reporte": None})

    background_tasks.add_task(_procesar_en_background, temp_path, id_lote)

    return {
        "status": "aceptado",
        "mensaje": "Proceso iniciado en background. Consulta GET /estado/ para ver progreso.",
        "archivo": file.filename,
    }


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 2 — Estado del proceso
# ══════════════════════════════════════════════════════════════════
@router.get("/estado/", tags=["Conciliación"])
async def estado():
    """Retorna el estado actual del proceso de conciliación."""
    return _leer_estado()


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 3 — Acumulación multi-período
# ══════════════════════════════════════════════════════════════════
@router.post("/upload-multi/", tags=["Multi-período"])
async def upload_multi(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    accion: Literal["agregar", "conciliar", "limpiar"] = Query(default="agregar")
):
    if accion == "limpiar":
        db.limpiar_transacciones_lote(2)
        return {"status": "ok", "mensaje": "Acumulación limpiada."}

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "Solo .xlsx o .xls")

    os.makedirs("data_samples", exist_ok=True)
    temp_path = f"data_samples/temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    if accion == "agregar":
        # Solo cargar, no procesar
        try:
            ingestor = DataIngestor(temp_path)
            df = ingestor.procesar_excel()
            cuenta = str(df["cuenta_contable"][0])
            regs = [
                (r["descripcion"], str(r["cuenta_contable"]), r["monto_centavos"],
                 r["n_diario"], str(r["localidad"]), str(r["periodo"]), str(r["tipo"]), 2)
                for r in df.to_dicts()
            ]
            del df; gc.collect()
            for i in range(0, len(regs), BATCH_SIZE):
                db.insertar_transacciones(regs[i:i+BATCH_SIZE])
            total = db.contar_pendientes_lote(cuenta, 2)
            return {"status": "acumulado", "archivo": file.filename,
                    "total_acumulado": total}
        finally:
            if os.path.exists(temp_path): os.remove(temp_path)

    # accion == "conciliar"
    _escribir_estado({"fase": "iniciando", "mensaje": "Iniciando conciliación multi-período...",
               "conciliados": 0, "pendientes": 0, "tasa": 0.0, "reporte": None})
    background_tasks.add_task(_procesar_en_background, temp_path, 2)
    return {"status": "aceptado", "mensaje": "Consulta GET /estado/ para ver progreso."}


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 4 — Estado acumulado multi-período
# ══════════════════════════════════════════════════════════════════
@router.get("/estado-acumulado/", tags=["Multi-período"])
async def estado_acumulado(cuenta: str = Query(...)):
    total = db.contar_pendientes_lote(cuenta, id_lote=2)
    return {"cuenta": cuenta, "registros_acumulados": total}

# ══════════════════════════════════════════════════════════════════
# ENDPOINT 5 — Descarga de reporte Excel
# ══════════════════════════════════════════════════════════════════
@router.get("/download-report/{filename}", tags=["Reportes"])
async def download_report(filename: str):
    """Descarga un reporte Excel generado previamente."""
    # Buscar en la carpeta de reportes
    ruta = os.path.join("reportes", filename)
    if not os.path.exists(ruta):
        # Intentar ruta directa
        if os.path.exists(filename):
            ruta = filename
        else:
            raise HTTPException(404, f"Reporte no encontrado: {filename}")
    return FileResponse(
        path=ruta,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 6 — Listar transacciones conciliadas o pendientes
# ══════════════════════════════════════════════════════════════════
@router.get("/transacciones/", tags=["Datos"])
async def listar_transacciones(
    estado: str = Query(..., description="CONCILIADO o PENDIENTE"),
    cuenta: str = Query(..., description="Número de cuenta contable"),
    page:   int = Query(default=1,   ge=1),
    limit:  int = Query(default=100, le=500),
):
    """Retorna registros paginados filtrados por estado y cuenta."""
    if estado not in ("CONCILIADO", "PENDIENTE"):
        raise HTTPException(400, "estado debe ser CONCILIADO o PENDIENTE")

    offset = (page - 1) * limit
    con = __import__("sqlite3").connect(db.ruta_db)
    cur = con.cursor()

    # Registros de la página actual
    cur.execute("""
        SELECT  t.id_transaccion,
                t.tipo,
                t.periodo,
                t.descripcion,
                t.localidad,
                ROUND(CAST(t.monto_centavos AS REAL) / 100, 2) AS monto,
                t.n_diario,
                t.id_conciliacion,
                COALESCE(c.fase_origen, NULL) AS fase_origen
        FROM    TRANSACCION t
        LEFT JOIN CONCILIACION c
               ON ABS(t.id_conciliacion) = c.id_conciliacion
        WHERE   t.estado_tx      = ?
          AND   t.cuenta_contable = ?
        ORDER BY COALESCE(c.fase_origen, 'ZZ'),
                 ABS(t.id_conciliacion) NULLS LAST,
                 t.id_transaccion
        LIMIT ? OFFSET ?
    """, (estado, cuenta, limit, offset))
    filas = cur.fetchall()

    # Total para paginación
    cur.execute("""
        SELECT COUNT(*)
        FROM   TRANSACCION
        WHERE  estado_tx = ? AND cuenta_contable = ?
    """, (estado, cuenta))
    total = cur.fetchone()[0] or 0
    con.close()

    return {
        "items": [
            {
                "id":          f[0],
                "tipo":        f[1],
                "periodo":     f[2],
                "descripcion": f[3],
                "localidad":   f[4],
                "monto":       f[5],
                "n_diario":    f[6],
                "grupo":       f[7],          # id_conciliacion
                "fase":        f[8],          # F1 / F2 / F3 / F4 / F5 / null
            }
            for f in filas
        ],
        "total":  total,
        "page":   page,
        "pages":  max(1, (total + limit - 1) // limit),
    }


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 7 — Inferir fases de conciliaciones antiguas (F?)
# ══════════════════════════════════════════════════════════════════
@router.post("/inferir-fases/", tags=["Mantenimiento"])
async def inferir_fases_background(background_tasks: BackgroundTasks):
    """
    Para conciliaciones antiguas con fase_origen='F?' — infiere la fase
    analizando el patrón de cada grupo y actualiza la DB sin re-procesar.
    """
    background_tasks.add_task(_inferir_fases_en_background)
    return {"status": "iniciado", "mensaje": "Inferencia de fases en curso. Consulta GET /estado/"}


def _inferir_fases_en_background():
    """
    Lógica de inferencia:
    - F1: grupo de exactamente 2 tx, mismo n_diario, misma localidad, montos opuestos exactos
    - F2: grupo ≥3 tx, mismo n_diario, misma localidad, suma exactamente cero
    - F3: grupo 2 tx, mismo n_diario, misma localidad, |suma| <= 5
    - F4: grupo 2 tx, distinto n_diario, misma localidad, montos opuestos exactos
    - F5: grupo 2 tx, distinto n_diario, distinta localidad (o cualquier combo restante)
    """
    import sqlite3, time
    _escribir_estado({**_leer_estado(), "fase": "procesando", "mensaje": "Infiriendo fases de conciliaciones antiguas..."})
    t0 = time.time()
    con = sqlite3.connect(db.ruta_db)
    cur = con.cursor()

    # Obtener todos los grupos con fase F? o NULL
    cur.execute("""
        SELECT id_conciliacion FROM CONCILIACION
        WHERE fase_origen = 'F?' OR fase_origen IS NULL
    """)
    grupos_sin_fase = [r[0] for r in cur.fetchall()]

    if not grupos_sin_fase:
        con.close()
        _escribir_estado({**_leer_estado(), "fase": "listo", "mensaje": "Todas las conciliaciones ya tienen fase asignada."})
        return

    actualizados = {"F1": 0, "F2": 0, "F3": 0, "F4": 0, "F5": 0}
    LOTE = 500

    for i in range(0, len(grupos_sin_fase), LOTE):
        batch_ids = grupos_sin_fase[i:i+LOTE]
        placeholders = ",".join("?" * len(batch_ids))

        # Obtener tx de todos los grupos del batch
        cur.execute(f"""
            SELECT id_conciliacion, n_diario, localidad, monto_centavos
            FROM   TRANSACCION
            WHERE  id_conciliacion IN ({placeholders})
            ORDER  BY id_conciliacion
        """, batch_ids)
        filas = cur.fetchall()

        # Agrupar por id_conciliacion
        from collections import defaultdict
        grupos = defaultdict(list)
        for gid, nd, loc, monto in filas:
            grupos[gid].append({"n_diario": nd, "localidad": loc, "monto": monto})

        updates = []
        for gid, txs in grupos.items():
            n = len(txs)
            suma = sum(t["monto"] for t in txs)
            mismo_ndiario  = len(set(t["n_diario"]  for t in txs)) == 1
            misma_localidad = len(set(t["localidad"] for t in txs)) == 1

            if n == 2 and mismo_ndiario and misma_localidad and suma == 0:
                fase = "F1"
            elif n >= 2 and mismo_ndiario and misma_localidad and suma == 0:
                fase = "F2"
            elif n >= 2 and mismo_ndiario and misma_localidad and abs(suma) <= 5:
                fase = "F3"
            elif n == 2 and misma_localidad and suma == 0:
                fase = "F4"
            else:
                fase = "F5"

            updates.append((fase, gid))
            actualizados[fase] += 1

        cur.executemany(
            "UPDATE CONCILIACION SET fase_origen = ? WHERE id_conciliacion = ?",
            updates
        )
        con.commit()

        if i % 5000 == 0:
            pct = min(100, int(i / len(grupos_sin_fase) * 100))
            _escribir_estado({**_leer_estado(),
                "mensaje": f"Infiriendo fases... {pct}% ({i:,}/{len(grupos_sin_fase):,} grupos)"})

    con.close()
    resumen = ", ".join(f"{f}:{v:,}" for f, v in actualizados.items() if v > 0)
    _escribir_estado({**_leer_estado(),
        "fase": "listo",
        "mensaje": f"Fases inferidas en {time.time()-t0:.1f}s — {resumen}"})
    print(f"✅ Fases inferidas: {resumen}")


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 8 — Historial de ejecuciones desde la DB
# Fuente de verdad universal: funciona en cualquier IP/origen
# ══════════════════════════════════════════════════════════════════
@router.get("/historial/", tags=["Datos"])
async def obtener_historial():
    """
    Retorna todas las ejecuciones completadas guardadas en la DB.
    No depende de localStorage — funciona desde cualquier IP/origen.
    """
    import sqlite3 as _sq3
    try:
        con = _sq3.connect(db.ruta_db)
        cur = con.cursor()

        # Una fila por lote procesado con sus estadísticas
        cur.execute("""
            SELECT
                t.id_lote,
                t.cuenta_contable                                          AS cuenta,
                COUNT(t.id_transaccion)                                    AS total,
                SUM(CASE WHEN t.estado_tx='CONCILIADO' THEN 1 ELSE 0 END) AS conciliados,
                SUM(CASE WHEN t.estado_tx='PENDIENTE'  THEN 1 ELSE 0 END) AS pendientes,
                MIN(t.periodo)                                             AS periodo,
                MAX(c.fecha_conciliacion)                                  AS fecha
            FROM TRANSACCION t
            LEFT JOIN CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
            GROUP BY t.id_lote, t.cuenta_contable
            ORDER BY t.id_lote DESC
        """)
        rows = cur.fetchall()
        con.close()

        resultado = []
        for row in rows:
            id_lote, cuenta, total, conciliados, pendientes, periodo, fecha = row
            conciliados = conciliados or 0
            pendientes  = pendientes  or 0
            total       = total       or 0
            tasa        = round((conciliados / total * 100), 2) if total else 0.0

            # Parsear periodo "2025/012" → mes/anio
            mes, anio = None, None
            if periodo:
                import re as _re
                m = _re.match(r'(\d{4})/(\d+)', periodo)
                if m:
                    anio = int(m.group(1))
                    mes  = int(m.group(2)) - 1   # 0-indexed como JS Date

            # Buscar el reporte más reciente para este lote
            ruta_reporte = ""
            carpeta = "reportes"
            if os.path.exists(carpeta):
                archivos = sorted(
                    [f for f in os.listdir(carpeta) if f.endswith(".xlsx")],
                    reverse=True
                )
                if archivos:
                    ruta_reporte = archivos[0]   # más reciente

            resultado.append({
                "id_lote":      id_lote,
                "cuenta":       cuenta or "—",
                "total":        total,
                "conciliados":  conciliados,
                "pendientes":   pendientes,
                "tasa":         tasa,
                "efectividad":  f"{tasa:.1f}%",
                "periodo":      periodo or "",
                "mes":          mes,
                "anio":         anio,
                "fecha":        fecha or "",
                "ruta_reporte": ruta_reporte,
            })

        return {"historial": resultado, "total": len(resultado)}

    except Exception as e:
        return {"historial": [], "total": 0, "error": str(e)}


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 9 — Estadísticas por fase para una cuenta
# Permite a F1/F2/F3/F4/F5 mostrar sus propios datos reales
# ══════════════════════════════════════════════════════════════════
@router.get("/stats-por-fase/", tags=["Datos"])
async def stats_por_fase(cuenta: str = Query(...)):
    """
    Retorna conteo de conciliados por fase (F1-F5) para una cuenta.
    Respuesta:
    {
      "cuenta": "299005060",
      "total_conciliados": 224822,
      "pendientes": 122643,
      "fases": {
        "F1": {"conciliados": 90000, "pct_sobre_conciliados": 40.0, "pct_sobre_total": 25.9},
        "F2": {...}, "F3": {...}, "F4": {...}, "F5": {...}
      }
    }
    """
    import sqlite3 as _sq3
    try:
        con = _sq3.connect(db.ruta_db)
        cur = con.cursor()

        # Totales generales
        cur.execute("""
            SELECT
                SUM(CASE WHEN estado_tx='CONCILIADO' THEN 1 ELSE 0 END),
                SUM(CASE WHEN estado_tx='PENDIENTE'  THEN 1 ELSE 0 END),
                COUNT(*)
            FROM TRANSACCION
            WHERE cuenta_contable = ?
        """, (cuenta,))
        row = cur.fetchone()
        total_conciliados = row[0] or 0
        total_pendientes  = row[1] or 0
        total_global      = row[2] or 0

        # Conteo por fase
        cur.execute("""
            SELECT c.fase_origen, COUNT(t.id_transaccion) AS n
            FROM   TRANSACCION t
            JOIN   CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
            WHERE  t.cuenta_contable = ?
              AND  t.estado_tx = 'CONCILIADO'
            GROUP BY c.fase_origen
            ORDER BY c.fase_origen
        """, (cuenta,))
        filas_fase = cur.fetchall()
        con.close()

        fases_resultado = {}
        for fase_key in ["F1", "F2", "F3", "F4", "F5"]:
            n = next((r[1] for r in filas_fase if r[0] == fase_key), 0)
            fases_resultado[fase_key] = {
                "conciliados":            n,
                "pct_sobre_conciliados":  round(n / total_conciliados * 100, 1) if total_conciliados else 0.0,
                "pct_sobre_total":        round(n / total_global * 100, 1)      if total_global      else 0.0,
            }

        return {
            "cuenta":            cuenta,
            "total_global":      total_global,
            "total_conciliados": total_conciliados,
            "pendientes":        total_pendientes,
            "pct_conciliados":   round(total_conciliados / total_global * 100, 1) if total_global else 0.0,
            "pct_pendientes":    round(total_pendientes  / total_global * 100, 1) if total_global else 0.0,
            "fases":             fases_resultado,
        }

    except Exception as e:
        return {"cuenta": cuenta, "error": str(e), "fases": {}}