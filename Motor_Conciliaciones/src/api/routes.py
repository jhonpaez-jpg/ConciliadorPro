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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# TAREA BACKGROUND â€” carga + motor completo
# Orden: F1â†’F2â†’F3â†’F4 (por localidad) â†’ F6gâ†’F7â†’F7b (global) â†’ F5 (Ãºltimo recurso)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
def _procesar_en_background(temp_path: str, id_lote: int):
    try:
        # â”€â”€ 1. Ingestar â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _escribir_estado({**_leer_estado(), "fase": "cargando", "mensaje": "Leyendo Excel y filtrando SIF82/TES82..."})
        t0 = time.time()

        ingestor = DataIngestor(temp_path)
        df_limpio = ingestor.procesar_excel()
        cuenta = str(df_limpio["cuenta_contable"][0])
        total_leido = len(df_limpio)
        print(f"ðŸ“¥ {total_leido:,} regs leÃ­dos en {time.time()-t0:.1f}s")

        # â”€â”€ 2. Insertar en DB por lotes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _escribir_estado({**_leer_estado(), "mensaje": f"Insertando {total_leido:,} registros en DB..."})
        # NO se limpia el lote anterior â€” cada ejecuciÃ³n tiene su propio id_lote Ãºnico
        registros = [
            (r["descripcion"], str(r["cuenta_contable"]), r["monto_centavos"],
             r["n_diario"], str(r["localidad"]), str(r["periodo"]), str(r["tipo"]), id_lote)
            for r in df_limpio.to_dicts()
        ]
        del df_limpio; gc.collect()

        for i in range(0, len(registros), BATCH_SIZE):
            db.insertar_transacciones(registros[i:i+BATCH_SIZE])
        del registros; gc.collect()
        print(f"ðŸ’¾ DB cargada en {time.time()-t0:.1f}s")

        # â”€â”€ 3. F1-F4: Motor por localidades â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _escribir_estado({**_leer_estado(), "fase": "procesando", "mensaje": "F1-F4: Ejecutando motor por localidades..."})
        localidades = db.obtener_localidades_unicas_por_lote(cuenta, id_lote)
        total_c = 0

        for idx, localidad in enumerate(localidades, 1):
            # Verificar cancelaciÃ³n en cada localidad
            if _leer_estado().get("fase") == "cancelado":
                print("âš ï¸ Proceso cancelado por el usuario.")
                return

            filas_db = db.obtener_pendientes_por_localidad(cuenta, localidad, id_lote)
            if not filas_db: continue
            txs = filas_a_transacciones(filas_db)
            del filas_db; gc.collect()

            _escribir_estado({**_leer_estado(), "mensaje": f"F1-F4 [{idx}/{len(localidades)}] Localidad {localidad}: {len(txs):,} regs"})
            engine = ReconciliationEngine()
            conciliadas, _ = engine.ejecutar_proceso_completo(txs)
            del txs; gc.collect()

            if conciliadas:
                from collections import defaultdict as _dd2
                por_fase = _dd2(list)
                for entry in conciliadas:
                    por_fase[entry["fase"]].append(entry["grupo"])
                for fase_label, grupos in por_fase.items():
                    if grupos:
                        db.registrar_conciliacion_masiva(grupos, fase_origen=fase_label)
                total_c += sum(len(entry["grupo"]) for entry in conciliadas)
            del conciliadas, engine; gc.collect()

        print(f"âœ… F1-F4 localidades: {total_c:,} conciliados")

        # â”€â”€ 4. F6g/F7/F7b â€” Subset Sum global sobre todos los pendientes â”€â”€â”€â”€
        if _leer_estado().get("fase") == "cancelado":
            print("âš ï¸ Proceso cancelado por el usuario.")
            return
        _escribir_estado({**_leer_estado(), "mensaje": "F6/F7: Subset Sum global sobre pendientes..."})

        filas_global = db.obtener_todos_pendientes(cuenta, id_lote)
        n_pendientes_global = len(filas_global)
        print(f"   F6/F7: {n_pendientes_global:,} transacciones pendientes tras F1-F4")

        if filas_global:
            txs_global = filas_a_transacciones(filas_global)
            del filas_global; gc.collect()

            engine_global = ReconciliationEngine()
            grupos_global = engine_global.ejecutar_f6_standalone(txs_global)
            del txs_global, engine_global; gc.collect()

            if grupos_global:
                por_fase_global = defaultdict(list)
                for entry in grupos_global:
                    por_fase_global[entry["fase"]].append(entry["grupo"])
                for fase_label, grupos in por_fase_global.items():
                    db.registrar_conciliacion_masiva(grupos, fase_origen=fase_label)
                n_tx_global = sum(len(entry["grupo"]) for entry in grupos_global)
                total_c += n_tx_global
                resumen = {k: sum(len(g) for g in v) for k, v in por_fase_global.items()}
                print(f"âœ… F6/F7: {len(grupos_global)} grupos, {n_tx_global:,} tx â€” {resumen}")
            else:
                print("   F6/F7: sin grupos encontrados")
        else:
            del filas_global

        # â”€â”€ 5. F5 â€” monto puro (Ãºltimo recurso) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _escribir_estado({**_leer_estado(), "mensaje": "F5: Conciliando por monto puro (Ãºltimo recurso)..."})
        f5 = db.conciliar_por_monto_puro(cuenta, id_lote)
        total_c += f5
        print(f"âœ… F5: {f5:,} conciliados por monto puro")

        # â”€â”€ 6. Reporte desde DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        _escribir_estado({**_leer_estado(), "mensaje": "Generando reporte..."})
        ruta = reporter.generar_excel_desde_db(db, cuenta, id_lote)

        pendientes_db = db.contar_pendientes_lote(cuenta, id_lote)
        tasa = (total_c / total_leido * 100) if total_leido else 0

        # Obtener perÃ­odo del lote
        periodos = db.obtener_periodos_disponibles(cuenta, id_lote)
        periodo_str = periodos[0] if periodos else None

        # Parsear mes/anio del perÃ­odo
        import re as _re
        mes_exec, anio_exec = None, None
        if periodo_str:
            _m = _re.match(r'(\d{4})/(\d+)', periodo_str)
            if _m:
                anio_exec = int(_m.group(1))
                mes_exec  = int(_m.group(2)) - 1  # 0-indexed

        # â”€â”€ 7. Registrar ejecuciÃ³n en historial permanente â”€â”€â”€â”€â”€â”€â”€â”€
        db.registrar_ejecucion(
            cuenta       = cuenta,
            total        = total_leido,
            conciliados  = total_c,
            pendientes   = pendientes_db,
            tasa         = round(tasa, 2),
            periodo      = periodo_str or "",
            mes          = mes_exec,
            anio         = anio_exec,
            ruta_reporte = ruta,
            id_lote      = id_lote,
        )

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
            "id_lote": id_lote,
        })
        print(f"ðŸ Todo listo: {total_c:,} conciliados ({tasa:.1f}%) en {time.time()-t0:.0f}s")

    except Exception as e:
        import traceback
        _escribir_estado({**_leer_estado(), "fase": "error", "mensaje": str(e)})
        print(f"âŒ Error background: {e}")
        traceback.print_exc()
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 1 â€” Subir archivo (responde inmediato, procesa en background)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.post("/upload-and-reconcile/", tags=["ConciliaciÃ³n"])
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

    id_lote = int(time.time())  # Ãºnico por ejecuciÃ³n â€” nunca sobreescribe datos anteriores
    _escribir_estado({"fase": "iniciando", "mensaje": "Archivo recibido, iniciando...",
               "conciliados": 0, "pendientes": 0, "tasa": 0.0, "reporte": None})

    background_tasks.add_task(_procesar_en_background, temp_path, id_lote)

    return {
        "status": "aceptado",
        "mensaje": "Proceso iniciado en background. Consulta GET /estado/ para ver progreso.",
        "archivo": file.filename,
    }


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 2 â€” Estado del proceso
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/estado/", tags=["ConciliaciÃ³n"])
async def estado():
    """Retorna el estado actual del proceso de conciliaciÃ³n."""
    return _leer_estado()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 2b â€” Cancelar proceso en curso
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.post("/cancelar/", tags=["ConciliaciÃ³n"])
async def cancelar():
    """
    Marca el proceso como cancelado. El hilo de background detecta la seÃ±al
    y se detiene en el prÃ³ximo punto de control.
    """
    estado_actual = _leer_estado()
    if estado_actual.get("fase") not in ("cargando", "procesando", "iniciando"):
        return {"status": "noop", "mensaje": "No hay proceso activo para cancelar."}
    _escribir_estado({**estado_actual, "fase": "cancelado", "mensaje": "Cancelado por el usuario."})
    return {"status": "ok", "mensaje": "SeÃ±al de cancelaciÃ³n enviada."}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 2c â€” Programar ejecuciÃ³n nocturna
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.post("/programar/", tags=["ConciliaciÃ³n"])
async def programar_ejecucion(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    hora: str = Query(..., description="HH:MM â€” hora de ejecuciÃ³n"),
    fecha: str = Query(default="", description="YYYY-MM-DD â€” vacÃ­o = hoy"),
    f2_timeout: int = Query(default=2),
    f3_timeout: int = Query(default=10),
    f4_timeout: int = Query(default=30),
    max_depth:  int = Query(default=5),
):
    """Guarda el archivo y registra la ejecuciÃ³n programada para la hora indicada."""
    import json as _json
    from datetime import datetime as _dt, date as _date

    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(400, "Solo .xlsx o .xls")

    # Validar hora
    try:
        _dt.strptime(hora, "%H:%M")
    except ValueError:
        raise HTTPException(400, "Formato de hora invÃ¡lido. Usa HH:MM")

    fecha_prog = fecha if fecha else _date.today().isoformat()

    # Guardar archivo en carpeta temporal permanente
    os.makedirs("data_samples/programados", exist_ok=True)
    ts = int(time.time())
    archivo_path = f"data_samples/programados/{ts}_{file.filename}"
    with open(archivo_path, "wb") as f:
        import shutil as _sh
        _sh.copyfileobj(file.file, f)

    config_json = _json.dumps({
        "f2_timeout": f2_timeout,
        "f3_timeout": f3_timeout,
        "f4_timeout": f4_timeout,
        "max_depth":  max_depth,
    })
    creado_en = _dt.now().strftime("%d/%m/%Y %H:%M")

    con = sqlite3.connect(db.ruta_db, timeout=30)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO EJECUCION_PROGRAMADA
            (fecha_programada, hora_programada, archivo_path, archivo_nombre,
             config_json, estado, creado_en)
        VALUES (?, ?, ?, ?, ?, 'PENDIENTE', ?)
    """, (fecha_prog, hora, archivo_path, file.filename, config_json, creado_en))
    prog_id = cur.lastrowid
    con.commit()
    con.close()

    # Iniciar el scheduler en background si no estÃ¡ corriendo
    background_tasks.add_task(_scheduler_tick)

    return {
        "status": "programado",
        "id": prog_id,
        "archivo": file.filename,
        "fecha": fecha_prog,
        "hora": hora,
        "mensaje": f"EjecuciÃ³n programada para el {fecha_prog} a las {hora}",
    }


@router.get("/programadas/", tags=["ConciliaciÃ³n"])
async def listar_programadas():
    """Lista todas las ejecuciones programadas pendientes y recientes."""
    con = sqlite3.connect(db.ruta_db, timeout=30)
    cur = con.cursor()
    cur.execute("""
        SELECT id, fecha_programada, hora_programada, archivo_nombre,
               estado, creado_en, ejecutado_en
        FROM EJECUCION_PROGRAMADA
        ORDER BY fecha_programada DESC, hora_programada DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    con.close()
    return {"programadas": [
        {
            "id": r[0], "fecha": r[1], "hora": r[2],
            "archivo": r[3], "estado": r[4],
            "creado_en": r[5], "ejecutado_en": r[6],
        }
        for r in rows
    ]}


@router.delete("/programadas/{prog_id}", tags=["ConciliaciÃ³n"])
async def cancelar_programada(prog_id: int):
    """Cancela una ejecuciÃ³n programada pendiente."""
    con = sqlite3.connect(db.ruta_db, timeout=30)
    cur = con.cursor()
    cur.execute("""
        UPDATE EJECUCION_PROGRAMADA SET estado='CANCELADO'
        WHERE id=? AND estado='PENDIENTE'
    """, (prog_id,))
    affected = cur.rowcount
    con.commit()
    con.close()
    if affected == 0:
        raise HTTPException(404, "EjecuciÃ³n no encontrada o ya procesada.")
    return {"status": "ok", "mensaje": "EjecuciÃ³n programada cancelada."}


@router.get("/programadas/proxima/", tags=["ConciliaciÃ³n"])
async def proxima_programada():
    """
    Retorna la prÃ³xima ejecuciÃ³n pendiente con el tiempo restante en segundos.
    Ãštil para que el frontend muestre una cuenta regresiva.
    """
    from datetime import datetime as _dt
    con = sqlite3.connect(db.ruta_db, timeout=30)
    cur = con.cursor()
    cur.execute("""
        SELECT id, fecha_programada, hora_programada, archivo_nombre, creado_en
        FROM EJECUCION_PROGRAMADA
        WHERE estado = 'PENDIENTE'
        ORDER BY fecha_programada ASC, hora_programada ASC
        LIMIT 1
    """)
    row = cur.fetchone()
    con.close()

    if not row:
        return {"proxima": None}

    prog_id, fecha_str, hora_str, archivo, creado_en = row
    try:
        dt_prog = _dt.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
        segundos_restantes = max(0, int((dt_prog - _dt.now()).total_seconds()))
        ya_paso = _dt.now() >= dt_prog
    except ValueError:
        segundos_restantes = 0
        ya_paso = False

    return {
        "proxima": {
            "id":                 prog_id,
            "fecha":              fecha_str,
            "hora":               hora_str,
            "archivo":            archivo,
            "creado_en":          creado_en,
            "segundos_restantes": segundos_restantes,
            "ya_paso":            ya_paso,
        }
    }


def _scheduler_tick():
    """
    Scheduler robusto de ejecuciones programadas.
    - Arranca un Ãºnico hilo daemon al iniciar el servidor
    - Verifica cada 30 segundos si hay ejecuciones que ejecutar
    - Al arrancar, recupera las que quedaron en EJECUTANDO (reinicio del servidor)
    - ComparaciÃ³n correcta: fecha+hora como datetime completo
    - Cada ejecuciÃ³n corre en su propio hilo para no bloquear el scheduler
    """
    import json as _json
    from datetime import datetime as _dt
    import threading as _th

    def _ejecutar_programada(prog_id: int, archivo_path: str, config_json: str):
        """Ejecuta una conciliaciÃ³n programada en un hilo separado."""
        try:
            _marcar_programada(prog_id, "EJECUTANDO")
            id_lote = int(time.time())
            print(f"ðŸ• Scheduler: iniciando prog_id={prog_id} â†’ lote {id_lote}")
            _procesar_en_background(archivo_path, id_lote)
            _marcar_programada(prog_id, "COMPLETADO")
            print(f"âœ… Scheduler: prog_id={prog_id} completado")
        except Exception as e:
            print(f"âŒ Scheduler: prog_id={prog_id} error: {e}")
            _marcar_programada(prog_id, "ERROR")

    def _run():
        print("ðŸ• Scheduler de ejecuciones programadas iniciado.")

        # Al arrancar: recuperar las que quedaron en EJECUTANDO por reinicio
        try:
            con = sqlite3.connect(db.ruta_db, timeout=30)
            cur = con.cursor()
            cur.execute("""
                UPDATE EJECUCION_PROGRAMADA
                SET estado = 'PENDIENTE'
                WHERE estado = 'EJECUTANDO'
            """)
            recuperadas = cur.rowcount
            con.commit()
            con.close()
            if recuperadas:
                print(f"ðŸ”„ Scheduler: {recuperadas} ejecuciÃ³n(es) recuperada(s) tras reinicio")
        except Exception as e:
            print(f"âš ï¸ Scheduler: error al recuperar pendientes: {e}")

        while True:
            try:
                ahora = _dt.now()

                con = sqlite3.connect(db.ruta_db, timeout=30)
                cur = con.cursor()
                # Traer todas las PENDIENTES â€” comparar como datetime completo en Python
                cur.execute("""
                    SELECT id, archivo_path, config_json,
                           fecha_programada, hora_programada
                    FROM EJECUCION_PROGRAMADA
                    WHERE estado = 'PENDIENTE'
                    ORDER BY fecha_programada ASC, hora_programada ASC
                """)
                pendientes = cur.fetchall()
                con.close()

                for prog_id, archivo_path, config_json, fecha_str, hora_str in pendientes:
                    # Construir datetime programado y comparar con ahora
                    try:
                        dt_prog = _dt.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
                    except ValueError:
                        print(f"âš ï¸ Scheduler: formato de fecha/hora invÃ¡lido en prog_id={prog_id}")
                        _marcar_programada(prog_id, "ERROR")
                        continue

                    # Solo ejecutar si ya llegÃ³ o pasÃ³ el momento programado
                    if ahora < dt_prog:
                        minutos_restantes = int((dt_prog - ahora).total_seconds() / 60)
                        print(f"â³ Scheduler: prog_id={prog_id} programado en {minutos_restantes} min "
                              f"({fecha_str} {hora_str})")
                        continue

                    # Verificar que el archivo existe
                    if not os.path.exists(archivo_path):
                        print(f"âŒ Scheduler: archivo no encontrado para prog_id={prog_id}: {archivo_path}")
                        _marcar_programada(prog_id, "ERROR")
                        continue

                    # Lanzar en hilo separado para no bloquear el scheduler
                    t = _th.Thread(
                        target=_ejecutar_programada,
                        args=(prog_id, archivo_path, config_json),
                        name=f"conciliacion_prog_{prog_id}",
                        daemon=True,
                    )
                    t.start()
                    print(f"ðŸš€ Scheduler: lanzando prog_id={prog_id} ({fecha_str} {hora_str})")

            except Exception as e:
                print(f"âŒ Scheduler tick error: {e}")

            time.sleep(30)  # verificar cada 30 segundos

    # Solo lanzar un hilo si no hay uno corriendo
    import threading as _th2
    for t in _th2.enumerate():
        if t.name == "conciliador_scheduler":
            return
    t = _th2.Thread(target=_run, name="conciliador_scheduler", daemon=True)
    t.start()


def _marcar_programada(prog_id: int, estado: str):
    from datetime import datetime as _dt
    con = sqlite3.connect(db.ruta_db, timeout=30)
    cur = con.cursor()
    cur.execute("""
        UPDATE EJECUCION_PROGRAMADA
        SET estado=?, ejecutado_en=?
        WHERE id=?
    """, (estado, _dt.now().strftime("%d/%m/%Y %H:%M"), prog_id))
    con.commit()
    con.close()


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 3 â€” AcumulaciÃ³n multi-perÃ­odo
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.post("/upload-multi/", tags=["Multi-perÃ­odo"])
async def upload_multi(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    accion: Literal["agregar", "conciliar", "limpiar"] = Query(default="agregar")
):
    if accion == "limpiar":
        db.limpiar_transacciones_lote(2)
        return {"status": "ok", "mensaje": "AcumulaciÃ³n limpiada."}

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
    _escribir_estado({"fase": "iniciando", "mensaje": "Iniciando conciliaciÃ³n multi-perÃ­odo...",
               "conciliados": 0, "pendientes": 0, "tasa": 0.0, "reporte": None})
    background_tasks.add_task(_procesar_en_background, temp_path, 2)
    return {"status": "aceptado", "mensaje": "Consulta GET /estado/ para ver progreso."}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 4 â€” Estado acumulado multi-perÃ­odo
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/estado-acumulado/", tags=["Multi-perÃ­odo"])
async def estado_acumulado(cuenta: str = Query(...)):
    total = db.contar_pendientes_lote(cuenta, id_lote=2)
    return {"cuenta": cuenta, "registros_acumulados": total}

# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 5 â€” Descarga de reporte Excel
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 5b â€” Reporte PDF profesional generado desde la DB
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/download-report-pdf/{filename}", tags=["Reportes"])
async def download_report_pdf(filename: str):
    """Genera un PDF profesional con KPIs, resumen por fase y muestra de transacciones."""
    import traceback as _tb
    import sqlite3 as _sq3
    from datetime import datetime as _dt

    ruta_xlsx = os.path.join("reportes", filename)
    if not os.path.exists(ruta_xlsx):
        if os.path.exists(filename):
            ruta_xlsx = filename
        else:
            raise HTTPException(404, f"Reporte no encontrado: {filename}")

    pdf_name = filename.replace(".xlsx", ".pdf").replace(".xls", ".pdf")
    ruta_pdf = os.path.join("reportes", pdf_name)

    necesita_generar = (
        not os.path.exists(ruta_pdf)
        or os.path.getmtime(ruta_xlsx) > os.path.getmtime(ruta_pdf)
    )

    if necesita_generar:
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                HRFlowable, PageBreak
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

            # â”€â”€ Colores corporativos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            AZUL_OSCURO  = colors.HexColor("#1e3a5f")
            AZUL_MEDIO   = colors.HexColor("#2563eb")
            AZUL_CLARO   = colors.HexColor("#dbeafe")
            VERDE        = colors.HexColor("#16a34a")
            VERDE_CLARO  = colors.HexColor("#dcfce7")
            ROJO         = colors.HexColor("#dc2626")
            ROJO_CLARO   = colors.HexColor("#fee2e2")
            GRIS_CLARO   = colors.HexColor("#f8fafc")
            GRIS_BORDE   = colors.HexColor("#e2e8f0")
            BLANCO       = colors.white

            # â”€â”€ Estilos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            styles = getSampleStyleSheet()
            st_titulo = ParagraphStyle("titulo",
                fontName="Helvetica-Bold", fontSize=22,
                textColor=BLANCO, alignment=TA_CENTER, spaceAfter=4)
            st_subtitulo = ParagraphStyle("subtitulo",
                fontName="Helvetica", fontSize=11,
                textColor=colors.HexColor("#93c5fd"), alignment=TA_CENTER)
            st_seccion = ParagraphStyle("seccion",
                fontName="Helvetica-Bold", fontSize=12,
                textColor=AZUL_OSCURO, spaceBefore=14, spaceAfter=6)
            st_normal = ParagraphStyle("normal",
                fontName="Helvetica", fontSize=9,
                textColor=colors.HexColor("#374151"), leading=13)
            st_pie = ParagraphStyle("pie",
                fontName="Helvetica", fontSize=7,
                textColor=colors.HexColor("#9ca3af"), alignment=TA_CENTER)
            st_kpi_val = ParagraphStyle("kpi_val",
                fontName="Helvetica-Bold", fontSize=20,
                textColor=AZUL_OSCURO, alignment=TA_CENTER)
            st_kpi_lbl = ParagraphStyle("kpi_lbl",
                fontName="Helvetica", fontSize=8,
                textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER)

            # â”€â”€ Leer datos de la DB â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            con = _sq3.connect(db.ruta_db)
            cur = con.cursor()

            # Buscar el lote mÃ¡s reciente que coincida con el reporte
            cur.execute("""
                SELECT h.id_lote, h.cuenta, h.total, h.conciliados, h.pendientes,
                       h.tasa, h.periodo, h.fecha
                FROM HISTORIAL_EJECUCION h
                WHERE h.ruta_reporte LIKE ?
                ORDER BY h.id DESC LIMIT 1
            """, (f"%{filename.replace('.xlsx','')}%",))
            row_h = cur.fetchone()

            if row_h:
                id_lote, cuenta, total, conciliados, pendientes, tasa, periodo, fecha_ej = row_h
            else:
                # Fallback: Ãºltimo lote disponible
                cur.execute("""
                    SELECT id_lote, cuenta_contable,
                           COUNT(*) as total,
                           SUM(CASE WHEN estado_tx='CONCILIADO' THEN 1 ELSE 0 END),
                           SUM(CASE WHEN estado_tx='PENDIENTE'  THEN 1 ELSE 0 END)
                    FROM TRANSACCION GROUP BY id_lote ORDER BY id_lote DESC LIMIT 1
                """)
                row_t = cur.fetchone()
                if not row_t:
                    raise ValueError("No hay datos en la base de datos.")
                id_lote, cuenta, total, conciliados, pendientes = row_t
                tasa = round(conciliados / total * 100, 2) if total else 0
                periodo, fecha_ej = "", _dt.now().strftime("%d/%m/%Y %H:%M")

            # Conteo por fase
            cur.execute("""
                SELECT
                    CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
                    COUNT(t.id_transaccion) AS n
                FROM TRANSACCION t
                JOIN CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
                WHERE t.id_lote = ? AND t.estado_tx = 'CONCILIADO'
                GROUP BY fase ORDER BY fase
            """, (id_lote,))
            fases_raw = cur.fetchall()
            fases = {r[0]: r[1] for r in fases_raw}

            # Muestra de conciliados (mÃ¡x 50 filas)
            cur.execute("""
                SELECT t.tipo, t.periodo, t.descripcion, t.localidad,
                       ROUND(CAST(t.monto_centavos AS REAL)/100, 2),
                       COALESCE(c.fase_origen,'?')
                FROM TRANSACCION t
                JOIN CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
                WHERE t.id_lote = ? AND t.estado_tx = 'CONCILIADO'
                ORDER BY c.fase_origen, ABS(t.id_conciliacion)
                LIMIT 50
            """, (id_lote,))
            muestra_conci = cur.fetchall()

            # Muestra de pendientes (mÃ¡x 30 filas)
            cur.execute("""
                SELECT tipo, periodo, descripcion, localidad,
                       ROUND(CAST(monto_centavos AS REAL)/100, 2)
                FROM TRANSACCION
                WHERE id_lote = ? AND estado_tx = 'PENDIENTE'
                ORDER BY ABS(monto_centavos) DESC
                LIMIT 30
            """, (id_lote,))
            muestra_pend = cur.fetchall()
            con.close()

            pendientes_real = total - conciliados
            fecha_gen = _dt.now().strftime("%d/%m/%Y %H:%M")

            # â”€â”€ Construir PDF â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            doc = SimpleDocTemplate(
                ruta_pdf, pagesize=A4,
                leftMargin=1.8*cm, rightMargin=1.8*cm,
                topMargin=1.5*cm, bottomMargin=1.5*cm,
            )
            page_w = A4[0] - 3.6*cm
            elems = []

            # â”€â”€ PORTADA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            portada_data = [[
                Paragraph("REPORTE DE CONCILIACIÃ“N CONTABLE", st_titulo),
            ]]
            portada = Table(portada_data, colWidths=[page_w])
            portada.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), AZUL_OSCURO),
                ("TOPPADDING",  (0,0), (-1,-1), 22),
                ("BOTTOMPADDING",(0,0),(-1,-1), 8),
                ("LEFTPADDING", (0,0), (-1,-1), 16),
                ("RIGHTPADDING",(0,0), (-1,-1), 16),
                ("ROUNDEDCORNERS", (0,0), (-1,-1), [8,8,8,8]),
            ]))
            elems.append(portada)

            sub_data = [[Paragraph(f"Cuenta: {cuenta}  |  PerÃ­odo: {periodo or 'â€”'}  |  Generado: {fecha_gen}", st_subtitulo)]]
            sub_t = Table(sub_data, colWidths=[page_w])
            sub_t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#1e40af")),
                ("TOPPADDING",  (0,0), (-1,-1), 8),
                ("BOTTOMPADDING",(0,0),(-1,-1), 10),
            ]))
            elems.append(sub_t)
            elems.append(Spacer(1, 18))

            # â”€â”€ KPIs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elems.append(Paragraph("Resumen Ejecutivo", st_seccion))
            elems.append(HRFlowable(width=page_w, thickness=1.5, color=AZUL_MEDIO, spaceAfter=10))

            def kpi_cell(valor, label, bg, fg_val=AZUL_OSCURO):
                return [
                    Paragraph(str(valor), ParagraphStyle("kv", fontName="Helvetica-Bold",
                        fontSize=18, textColor=fg_val, alignment=TA_CENTER)),
                    Paragraph(label, ParagraphStyle("kl", fontName="Helvetica",
                        fontSize=8, textColor=colors.HexColor("#6b7280"), alignment=TA_CENTER)),
                ]

            kpi_w = page_w / 4 - 4
            kpi_data = [[
                kpi_cell(f"{total:,}", "Total Registros", GRIS_CLARO),
                kpi_cell(f"{conciliados:,}", "Conciliados", VERDE_CLARO, VERDE),
                kpi_cell(f"{pendientes_real:,}", "Pendientes", ROJO_CLARO, ROJO),
                kpi_cell(f"{tasa:.1f}%", "Efectividad", AZUL_CLARO, AZUL_MEDIO),
            ]]
            kpi_t = Table(kpi_data, colWidths=[kpi_w]*4, rowHeights=[None])
            kpi_t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (0,-1), GRIS_CLARO),
                ("BACKGROUND", (1,0), (1,-1), VERDE_CLARO),
                ("BACKGROUND", (2,0), (2,-1), ROJO_CLARO),
                ("BACKGROUND", (3,0), (3,-1), AZUL_CLARO),
                ("BOX",        (0,0), (0,-1), 1, GRIS_BORDE),
                ("BOX",        (1,0), (1,-1), 1, colors.HexColor("#86efac")),
                ("BOX",        (2,0), (2,-1), 1, colors.HexColor("#fca5a5")),
                ("BOX",        (3,0), (3,-1), 1, colors.HexColor("#93c5fd")),
                ("TOPPADDING",    (0,0), (-1,-1), 12),
                ("BOTTOMPADDING", (0,0), (-1,-1), 12),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
            ]))
            elems.append(kpi_t)
            elems.append(Spacer(1, 18))

            # â”€â”€ RESUMEN POR FASE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elems.append(Paragraph("Desglose por Fase de ConciliaciÃ³n", st_seccion))
            elems.append(HRFlowable(width=page_w, thickness=1.5, color=AZUL_MEDIO, spaceAfter=10))

            fase_descripciones = {
                "F1":  "Fast-Pass â€” Coincidencias exactas 1:1 (n_diario + localidad + monto)",
                "F2":  "Subset Sum â€” Grupos N:N con suma cero (mismo n_diario y localidad)",
                "F3":  "Tolerancia â€” Grupos con diferencia â‰¤ 5 centavos",
                "F4":  "Localidad â€” Parejas exactas por monto + localidad (sin n_diario)",
                "F5":  "Monto Puro â€” Parejas exactas solo por monto (Ãºltimo recurso 1:1)",
                "F6":  "Subset Sum Global â€” N positivos â†’ 1 negativo (programaciÃ³n dinÃ¡mica)",
                "F7":  "Final Cleaning â€” 1 positivo â†’ N negativos (programaciÃ³n dinÃ¡mica)",
                "F7b": "Final Cleaning B â€” Positivos restantes â†’ N negativos",
            }

            fase_hdr = [
                Paragraph("Fase", ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO, alignment=TA_CENTER)),
                Paragraph("DescripciÃ³n", ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO)),
                Paragraph("Conciliados", ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO, alignment=TA_RIGHT)),
                Paragraph("% del Total", ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO, alignment=TA_RIGHT)),
                Paragraph("% Conciliados", ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO, alignment=TA_RIGHT)),
            ]
            fase_rows = [fase_hdr]
            for fk in ["F1","F2","F3","F4","F5","F6","F7","F7b"]:
                n = fases.get(fk, 0)
                if n == 0:
                    continue
                pct_total = round(n / total * 100, 1) if total else 0
                pct_conci = round(n / conciliados * 100, 1) if conciliados else 0
                fase_rows.append([
                    Paragraph(fk, ParagraphStyle("fc", fontName="Helvetica-Bold", fontSize=9, textColor=AZUL_OSCURO, alignment=TA_CENTER)),
                    Paragraph(fase_descripciones.get(fk, fk), st_normal),
                    Paragraph(f"{n:,}", ParagraphStyle("fn", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)),
                    Paragraph(f"{pct_total}%", ParagraphStyle("fn", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)),
                    Paragraph(f"{pct_conci}%", ParagraphStyle("fn", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT)),
                ])

            if len(fase_rows) > 1:
                fase_t = Table(fase_rows, colWidths=[1.2*cm, page_w-8.2*cm, 2.5*cm, 2.2*cm, 2.3*cm])
                fase_style = [
                    ("BACKGROUND",    (0,0), (-1,0),  AZUL_OSCURO),
                    ("ROWBACKGROUNDS",(0,1), (-1,-1), [BLANCO, GRIS_CLARO]),
                    ("GRID",          (0,0), (-1,-1), 0.4, GRIS_BORDE),
                    ("TOPPADDING",    (0,0), (-1,-1), 6),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                    ("LEFTPADDING",   (0,0), (-1,-1), 8),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                    ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ]
                fase_t.setStyle(TableStyle(fase_style))
                elems.append(fase_t)
            elems.append(Spacer(1, 18))

            # â”€â”€ MUESTRA CONCILIADOS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if muestra_conci:
                elems.append(Paragraph(f"Muestra de Transacciones Conciliadas (primeras {len(muestra_conci)})", st_seccion))
                elems.append(HRFlowable(width=page_w, thickness=1.5, color=VERDE, spaceAfter=10))

                mc_hdr = ["Tipo", "PerÃ­odo", "DescripciÃ³n", "Localidad", "Monto (COP)", "Fase"]
                mc_hdr_row = [Paragraph(h, ParagraphStyle("mh", fontName="Helvetica-Bold",
                    fontSize=8, textColor=BLANCO, alignment=TA_CENTER)) for h in mc_hdr]
                mc_rows = [mc_hdr_row]
                for r in muestra_conci:
                    tipo, per, desc, loc, monto, fase = r
                    monto_fmt = f"{monto:,.2f}" if monto else "0.00"
                    color_monto = ROJO if (monto or 0) < 0 else VERDE
                    mc_rows.append([
                        Paragraph(str(tipo or ""), st_normal),
                        Paragraph(str(per or ""), st_normal),
                        Paragraph(str(desc or "")[:60], st_normal),
                        Paragraph(str(loc or ""), st_normal),
                        Paragraph(monto_fmt, ParagraphStyle("mn", fontName="Helvetica",
                            fontSize=8, textColor=color_monto, alignment=TA_RIGHT)),
                        Paragraph(str(fase or ""), ParagraphStyle("mf", fontName="Helvetica-Bold",
                            fontSize=8, textColor=AZUL_MEDIO, alignment=TA_CENTER)),
                    ])

                mc_t = Table(mc_rows, colWidths=[1.2*cm, 2*cm, page_w-10.4*cm, 2.5*cm, 2.7*cm, 1*cm])
                mc_t.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#166534")),
                    ("ROWBACKGROUNDS",(0,1), (-1,-1), [BLANCO, VERDE_CLARO]),
                    ("GRID",          (0,0), (-1,-1), 0.3, GRIS_BORDE),
                    ("TOPPADDING",    (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("LEFTPADDING",   (0,0), (-1,-1), 6),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                    ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ]))
                elems.append(mc_t)
                elems.append(Spacer(1, 18))

            # â”€â”€ MUESTRA PENDIENTES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            if muestra_pend:
                elems.append(Paragraph(f"Muestra de Transacciones Pendientes (top {len(muestra_pend)} por monto)", st_seccion))
                elems.append(HRFlowable(width=page_w, thickness=1.5, color=ROJO, spaceAfter=10))

                mp_hdr = ["Tipo", "PerÃ­odo", "DescripciÃ³n", "Localidad", "Monto (COP)"]
                mp_hdr_row = [Paragraph(h, ParagraphStyle("ph", fontName="Helvetica-Bold",
                    fontSize=8, textColor=BLANCO, alignment=TA_CENTER)) for h in mp_hdr]
                mp_rows = [mp_hdr_row]
                for r in muestra_pend:
                    tipo, per, desc, loc, monto = r
                    monto_fmt = f"{monto:,.2f}" if monto else "0.00"
                    color_monto = ROJO if (monto or 0) < 0 else VERDE
                    mp_rows.append([
                        Paragraph(str(tipo or ""), st_normal),
                        Paragraph(str(per or ""), st_normal),
                        Paragraph(str(desc or "")[:60], st_normal),
                        Paragraph(str(loc or ""), st_normal),
                        Paragraph(monto_fmt, ParagraphStyle("pm", fontName="Helvetica",
                            fontSize=8, textColor=color_monto, alignment=TA_RIGHT)),
                    ])

                mp_t = Table(mp_rows, colWidths=[1.2*cm, 2*cm, page_w-8.9*cm, 2.5*cm, 2.7*cm])
                mp_t.setStyle(TableStyle([
                    ("BACKGROUND",    (0,0), (-1,0),  colors.HexColor("#991b1b")),
                    ("ROWBACKGROUNDS",(0,1), (-1,-1), [BLANCO, ROJO_CLARO]),
                    ("GRID",          (0,0), (-1,-1), 0.3, GRIS_BORDE),
                    ("TOPPADDING",    (0,0), (-1,-1), 4),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("LEFTPADDING",   (0,0), (-1,-1), 6),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                    ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ]))
                elems.append(mp_t)
                elems.append(Spacer(1, 14))

            # â”€â”€ PIE DE PÃGINA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            elems.append(HRFlowable(width=page_w, thickness=0.5, color=GRIS_BORDE))
            elems.append(Spacer(1, 6))
            elems.append(Paragraph(
                f"Conciliador Pro  Â·  Generado el {fecha_gen}  Â·  Archivo: {filename}  Â·  "
                f"Total procesado: {total:,} registros",
                st_pie
            ))

            doc.build(elems)

        except ImportError as e:
            print(f"âŒ PDF ImportError: {e}")
            raise HTTPException(500, f"Dependencia faltante: {e}. Ejecuta: pip install reportlab openpyxl")
        except Exception as e:
            print(f"âŒ PDF Error: {e}")
            print(_tb.format_exc())
            raise HTTPException(500, f"Error generando PDF: {e}")

    return FileResponse(path=ruta_pdf, media_type="application/pdf", filename=pdf_name)


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 6 â€” Listar transacciones conciliadas o pendientes
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/transacciones/", tags=["Datos"])
async def listar_transacciones(
    estado: str = Query(..., description="CONCILIADO o PENDIENTE"),
    cuenta: str = Query(..., description="NÃºmero de cuenta contable"),
    page:   int = Query(default=1,   ge=1),
    limit:  int = Query(default=100, le=500),
):
    """Retorna registros paginados filtrados por estado y cuenta."""
    if estado not in ("CONCILIADO", "PENDIENTE"):
        raise HTTPException(400, "estado debe ser CONCILIADO o PENDIENTE")

    offset = (page - 1) * limit
    con = __import__("sqlite3").connect(db.ruta_db)
    cur = con.cursor()

    # Registros de la pÃ¡gina actual
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

    # Total para paginaciÃ³n
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


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 7 â€” Inferir fases de conciliaciones antiguas (F?)
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.post("/inferir-fases/", tags=["Mantenimiento"])
async def inferir_fases_background(background_tasks: BackgroundTasks):
    """
    Para conciliaciones antiguas con fase_origen='F?' â€” infiere la fase
    analizando el patrÃ³n de cada grupo y actualiza la DB sin re-procesar.
    """
    background_tasks.add_task(_inferir_fases_en_background)
    return {"status": "iniciado", "mensaje": "Inferencia de fases en curso. Consulta GET /estado/"}


def _inferir_fases_en_background():
    """
    LÃ³gica de inferencia:
    - F1: grupo de exactamente 2 tx, mismo n_diario, misma localidad, montos opuestos exactos
    - F2: grupo â‰¥3 tx, mismo n_diario, misma localidad, suma exactamente cero
    - F3: grupo 2 tx, mismo n_diario, misma localidad, |suma| <= 5
    - F4: grupo 2 tx, distinto n_diario, misma localidad, montos opuestos exactos
    - F5: grupo 2 tx, distinto n_diario, distinta localidad (o cualquier combo restante)
    """
    import sqlite3, time
    _escribir_estado({**_leer_estado(), "fase": "procesando", "mensaje": "Infiriendo fases de conciliaciones antiguas..."})
    t0 = time.time()
    con = sqlite3.connect(db.ruta_db, timeout=30)
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
        "mensaje": f"Fases inferidas en {time.time()-t0:.1f}s â€” {resumen}"})
    print(f"âœ… Fases inferidas: {resumen}")


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 8 â€” Historial de ejecuciones desde la DB
# Fuente de verdad universal: funciona en cualquier IP/origen
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/historial/", tags=["Datos"])
async def obtener_historial():
    """
    Retorna todas las ejecuciones desde HISTORIAL_EJECUCION.
    Fuente de verdad universal â€” funciona desde cualquier IP/dispositivo.
    Cada conciliaciÃ³n queda registrada permanentemente, nunca se sobreescribe.
    """
    import sqlite3 as _sq3
    try:
        con = _sq3.connect(db.ruta_db)
        cur = con.cursor()

        # Asegurar que la tabla existe (por si la DB es antigua)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS HISTORIAL_EJECUCION (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha        TEXT    NOT NULL,
                cuenta       TEXT    NOT NULL,
                total        INTEGER NOT NULL DEFAULT 0,
                conciliados  INTEGER NOT NULL DEFAULT 0,
                pendientes   INTEGER NOT NULL DEFAULT 0,
                tasa         REAL    NOT NULL DEFAULT 0.0,
                periodo      TEXT    DEFAULT '',
                mes          INTEGER DEFAULT NULL,
                anio         INTEGER DEFAULT NULL,
                ruta_reporte TEXT    DEFAULT '',
                id_lote      INTEGER DEFAULT NULL
            )
        """)
        con.commit()

        cur.execute("""
            SELECT id, fecha, cuenta, total, conciliados, pendientes,
                   tasa, periodo, mes, anio, ruta_reporte, id_lote
            FROM   HISTORIAL_EJECUCION
            ORDER  BY id DESC
        """)
        rows = cur.fetchall()
        con.close()

        resultado = []
        for row in rows:
            id_, fecha, cuenta, total, conciliados, pendientes, tasa, periodo, mes, anio, ruta_reporte, id_lote = row
            resultado.append({
                "id":           id_,
                "fecha":        fecha or "",
                "cuenta":       cuenta or "â€”",
                "total":        total or 0,
                "conciliados":  conciliados or 0,
                "pendientes":   pendientes or 0,
                "tasa":         tasa or 0.0,
                "efectividad":  f"{(tasa or 0.0):.1f}%",
                "periodo":      periodo or "",
                "mes":          mes,
                "anio":         anio,
                "ruta_reporte": ruta_reporte or "",
                "id_lote":      id_lote,
            })

        return {"historial": resultado, "total": len(resultado)}

    except Exception as e:
        return {"historial": [], "total": 0, "error": str(e)}


# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# ENDPOINT 9 â€” EstadÃ­sticas por fase para una cuenta
# Permite a F1/F2/F3/F4/F5 mostrar sus propios datos reales
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
@router.get("/stats-por-fase/", tags=["Datos"])
async def stats_por_fase(cuenta: str = Query(...), id_lote: int = Query(...)):
    """
    Retorna conteo de conciliados por fase para una cuenta y lote especÃ­fico.
    El id_lote identifica unÃ­vocamente una ejecuciÃ³n â€” garantiza datos del mes correcto.
    """
    import sqlite3 as _sq3
    try:
        con = _sq3.connect(db.ruta_db)
        cur = con.cursor()

        # Totales del lote especÃ­fico
        cur.execute("""
            SELECT
                SUM(CASE WHEN estado_tx='CONCILIADO' THEN 1 ELSE 0 END),
                SUM(CASE WHEN estado_tx='PENDIENTE'  THEN 1 ELSE 0 END),
                COUNT(*)
            FROM TRANSACCION
            WHERE cuenta_contable = ? AND id_lote = ?
        """, (cuenta, id_lote))
        row = cur.fetchone()
        total_conciliados = row[0] or 0
        total_pendientes  = row[1] or 0
        total_global      = row[2] or 0

        # Conteo por fase del lote â€” agrupa F6g dentro de F6 para compatibilidad
        cur.execute("""
            SELECT
                CASE WHEN c.fase_origen = 'F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
                COUNT(t.id_transaccion) AS n
            FROM   TRANSACCION t
            JOIN   CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
            WHERE  t.cuenta_contable = ? AND t.id_lote = ?
              AND  t.estado_tx = 'CONCILIADO'
            GROUP BY fase
            ORDER BY fase
        """, (cuenta, id_lote))
        filas_fase = cur.fetchall()
        con.close()

        fases_resultado = {}
        for fase_key in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F7b"]:
            n = next((r[1] for r in filas_fase if r[0] == fase_key), 0)
            fases_resultado[fase_key] = {
                "conciliados":           n,
                "pct_sobre_conciliados": round(n / total_conciliados * 100, 1) if total_conciliados else 0.0,
                "pct_sobre_total":       round(n / total_global * 100, 1)      if total_global      else 0.0,
            }

        return {
            "cuenta":            cuenta,
            "id_lote":           id_lote,
            "total_global":      total_global,
            "total_conciliados": total_conciliados,
            "pendientes":        total_pendientes,
            "pct_conciliados":   round(total_conciliados / total_global * 100, 1) if total_global else 0.0,
            "pct_pendientes":    round(total_pendientes  / total_global * 100, 1) if total_global else 0.0,
            "fases":             fases_resultado,
        }

    except Exception as e:
        return {"cuenta": cuenta, "id_lote": id_lote, "error": str(e), "fases": {}}
