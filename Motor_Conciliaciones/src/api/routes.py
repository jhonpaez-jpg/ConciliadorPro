from fastapi import APIRouter, UploadFile, File, HTTPException, Query, BackgroundTasks
from fastapi.responses import FileResponse
from typing import Literal
import shutil, os, gc, time
from collections import defaultdict
from src.data.ingestor import DataIngestor
from src.data.db_manager import DatabaseManager
from src.core.engine import ReconciliationEngine
from src.core.models import Transaccion
from src.utils.reporter import ReconciliationReporter
from src.data.db_connection import engine, IS_POSTGRES
from sqlalchemy import text as _sql

router = APIRouter()
db = DatabaseManager("conciliacion.db")
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
        return {
            "fase": "idle",
            "mensaje": "",
            "conciliados": 0,
            "pendientes": 0,
            "tasa": 0.0,
            "reporte": None,
        }


def _escribir_estado(estado: dict):
    import json

    with open(_ESTADO_FILE, "w") as f:
        json.dump(estado, f)


# Inicializar si no existe
if not os.path.exists(_ESTADO_FILE):
    _escribir_estado(
        {
            "fase": "idle",
            "mensaje": "",
            "conciliados": 0,
            "pendientes": 0,
            "tasa": 0.0,
            "reporte": None,
        }
    )


def filas_a_transacciones(filas_db):
    return [
        Transaccion(
            id_transaccion=f[0],
            descripcion=f[1],
            cuenta_contable=f[2],
            monto_centavos=f[3],
            n_diario=f[4],
            localidad=str(f[5]),
            periodo=str(f[6]),
            tipo=str(f[7]),
            id_lote=f[8],
        )
        for f in filas_db
    ]


def _registrar_intento(cuenta: str, id_lote: int, conciliados: int, total: int, estado: str):
    """Registra en historial cualquier intento: completado, cancelado o con error."""
    from datetime import datetime as _dt
    import re as _re2

    try:
        tasa = round(conciliados / total * 100, 2) if total else 0.0
        pendientes = total - conciliados
        periodos = db.obtener_periodos_disponibles(cuenta, id_lote) if total > 0 else []
        periodo_str = periodos[0] if periodos else ""
        mes_e, anio_e = None, None
        if periodo_str:
            _m2 = _re2.match(r"(\d{4})/(\d+)", periodo_str)
            if _m2:
                anio_e = int(_m2.group(1))
                mes_e = int(_m2.group(2)) - 1
        with engine.begin() as con:
            con.execute(
                _sql("""
                INSERT INTO historial_ejecucion
                    (fecha, cuenta, total, conciliados, pendientes, tasa,
                     periodo, mes, anio, ruta_reporte, id_lote, estado)
                VALUES
                    (:fecha, :cta, :total, :conci, :pend, :tasa,
                     :per, :mes, :anio, :ruta, :lote, :estado)
            """),
                {
                    "fecha": _dt.now().strftime("%d/%m/%Y %H:%M"),
                    "cta": cuenta,
                    "total": total,
                    "conci": conciliados,
                    "pend": pendientes,
                    "tasa": tasa,
                    "per": periodo_str,
                    "mes": mes_e,
                    "anio": anio_e,
                    "ruta": "",
                    "lote": id_lote,
                    "estado": estado,
                },
            )
    except Exception as _e:
        print(f"⚠️ No se pudo registrar intento en historial: {_e}")


# TAREA BACKGROUND – carga + motor completo
# Orden: F1→F2→F3→F4 (por localidad) → F6g→F7→F7b (global) → F5 (último recurso)
def _procesar_en_background(temp_path: str, id_lote: int):
    try:
        # ── 1. Ingestar ──────────────────────────────────────────────────────
        _escribir_estado(
            {
                **_leer_estado(),
                "fase": "cargando",
                "mensaje": "Leyendo Excel y filtrando SIF82/TES82...",
            }
        )
        t0 = time.time()
        ingestor = DataIngestor(temp_path)
        df_limpio = ingestor.procesar_excel()
        cuenta = str(df_limpio["cuenta_contable"][0])
        total_leido = len(df_limpio)
        print(f"🔥 {total_leido:,} regs leídos en {time.time()-t0:.1f}s")

        # ── 2. Insertar en DB por lotes ──────────────────────────────────────
        _escribir_estado(
            {**_leer_estado(), "mensaje": f"Insertando {total_leido:,} registros en DB..."}
        )
        registros = [
            (
                r["descripcion"],
                str(r["cuenta_contable"]),
                r["monto_centavos"],
                r["n_diario"],
                str(r["localidad"]),
                str(r["periodo"]),
                str(r["tipo"]),
                id_lote,
            )
            for r in df_limpio.to_dicts()
        ]
        del df_limpio
        gc.collect()

        for i in range(0, len(registros), BATCH_SIZE):
            db.insertar_transacciones(registros[i : i + BATCH_SIZE])
        del registros
        gc.collect()
        print(f"💾 DB cargada en {time.time()-t0:.1f}s")

        # ── 3. F1-F4: Motor por localidades ─────────────────────────────────
        _escribir_estado(
            {
                **_leer_estado(),
                "fase": "procesando",
                "mensaje": "F1-F4: Ejecutando motor por localidades...",
            }
        )
        localidades = db.obtener_localidades_unicas_por_lote(cuenta, id_lote)
        total_c = 0

        for idx, localidad in enumerate(localidades, 1):
            # Verificar cancelación en cada localidad
            if _leer_estado().get("fase") == "cancelado":
                print("⚠️ Proceso cancelado por el usuario.")
                _registrar_intento(cuenta, id_lote, total_c, total_leido, "CANCELADO")
                return

            filas_db = db.obtener_pendientes_por_localidad(cuenta, localidad, id_lote)
            if not filas_db:
                continue
            txs = filas_a_transacciones(filas_db)
            del filas_db
            gc.collect()
            _escribir_estado(
                {
                    **_leer_estado(),
                    "mensaje": f"F1-F4 [{idx}/{len(localidades)}] Localidad {localidad}: {len(txs):,} regs",
                }
            )
            engine_local = ReconciliationEngine()
            conciliadas, _ = engine_local.ejecutar_proceso_completo(txs)
            del txs
            gc.collect()

            if conciliadas:
                from collections import defaultdict as _dd2

                por_fase = _dd2(list)
                for entry in conciliadas:
                    por_fase[entry["fase"]].append(entry["grupo"])
                for fase_label, grupos in por_fase.items():
                    if grupos:
                        db.registrar_conciliacion_masiva(grupos, fase_origen=fase_label)
                total_c += sum(len(entry["grupo"]) for entry in conciliadas)
            del conciliadas, engine_local
            gc.collect()

        print(f"✅ F1-F4 localidades: {total_c:,} conciliados")

        # ── 4. F6g/F7/F7b – Subset Sum global sobre todos los pendientes ─────
        if _leer_estado().get("fase") == "cancelado":
            print("⚠️ Proceso cancelado por el usuario.")
            _registrar_intento(cuenta, id_lote, total_c, total_leido, "CANCELADO")
            return

        _escribir_estado(
            {**_leer_estado(), "mensaje": "F6/F7: Subset Sum global sobre pendientes..."}
        )
        filas_global = db.obtener_todos_pendientes(cuenta, id_lote)
        n_pendientes_global = len(filas_global)
        print(f"   F6/F7: {n_pendientes_global:,} transacciones pendientes tras F1-F4")

        if filas_global:
            txs_global = filas_a_transacciones(filas_global)
            del filas_global
            gc.collect()

            t_f6 = time.time()
            engine_global = ReconciliationEngine()
            grupos_global = engine_global.ejecutar_f6_standalone(txs_global)
            print(f"   F6/F7 algoritmo: {time.time()-t_f6:.1f}s")
            del txs_global, engine_global
            gc.collect()

            if grupos_global:
                por_fase_global = defaultdict(list)
                for entry in grupos_global:
                    por_fase_global[entry["fase"]].append(entry["grupo"])
                for fase_label, grupos in por_fase_global.items():
                    t_db = time.time()
                    db.registrar_conciliacion_masiva(grupos, fase_origen=fase_label)
                    print(f"   F6/F7 DB write ({fase_label}, {len(grupos)} grupos): {time.time()-t_db:.1f}s")
                n_tx_global = sum(len(entry["grupo"]) for entry in grupos_global)
                total_c += n_tx_global
                resumen = {k: sum(len(g) for g in v) for k, v in por_fase_global.items()}
                print(f"✅ F6/F7: {len(grupos_global)} grupos, {n_tx_global:,} tx – {resumen}")
            else:
                print("   F6/F7: sin grupos encontrados")
        else:
            del filas_global

        # ── 5. F5 – monto puro (último recurso) ─────────────────────────────
        _escribir_estado(
            {**_leer_estado(), "mensaje": "F5: Conciliando por monto puro (último recurso)..."}
        )
        f5 = db.conciliar_por_monto_puro(cuenta, id_lote)
        total_c += f5
        print(f"✅ F5: {f5:,} conciliados por monto puro")

        # ── 6. Reporte desde DB ──────────────────────────────────────────────
        _escribir_estado({**_leer_estado(), "mensaje": "Generando reporte..."})
        ruta = reporter.generar_excel_desde_db(db, cuenta, id_lote)
        pendientes_db = db.contar_pendientes_lote(cuenta, id_lote)
        tasa = (total_c / total_leido * 100) if total_leido else 0

        # Obtener período del lote
        periodos = db.obtener_periodos_disponibles(cuenta, id_lote)
        periodo_str = periodos[0] if periodos else None

        # Parsear mes/anio del período
        import re as _re

        mes_exec, anio_exec = None, None
        if periodo_str:
            _m = _re.match(r"(\d{4})/(\d+)", periodo_str)
            if _m:
                anio_exec = int(_m.group(1))
                mes_exec = int(_m.group(2)) - 1  # 0-indexed

        # ── 7. Registrar ejecución en historial permanente ───────────────────
        db.registrar_ejecucion(
            cuenta=cuenta,
            total=total_leido,
            conciliados=total_c,
            pendientes=pendientes_db,
            tasa=round(tasa, 2),
            periodo=periodo_str or "",
            mes=mes_exec,
            anio=anio_exec,
            ruta_reporte=ruta,
            id_lote=id_lote,
        )

        _escribir_estado(
            {
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
            }
        )

        print(f"🎉 Todo listo: {total_c:,} conciliados ({tasa:.1f}%) en {time.time()-t0:.0f}s")

    except Exception as e:
        import traceback

        _escribir_estado({**_leer_estado(), "fase": "error", "mensaje": str(e)})
        print(f"❌ Error background: {e}")
        traceback.print_exc()

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 0 — Validar archivo antes de ejecutar
# Verifica período único sin iniciar el proceso completo
# ══════════════════════════════════════════════════════════════════
@router.post("/validar-archivo/", tags=["Conciliación"])
async def validar_archivo(file: UploadFile = File(...)):
    """
    Lee el archivo Excel y verifica que tenga un solo período contable.
    Responde rápido sin iniciar la conciliación.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx o .xls")

    import tempfile, os as _os

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    try:
        import shutil as _sh

        _sh.copyfileobj(file.file, tmp)
        tmp.close()

        ingestor = DataIngestor(tmp.path if hasattr(tmp, "path") else tmp.name)
        df = ingestor._leer_hoja_correcta()
        df.columns = [c.strip() for c in df.columns]

        # Detectar columna de período
        col_periodo = next(
            (c for c in ["Período", "Periodo", "período", "periodo", "PERIODO"] if c in df.columns),
            None,
        )

        if col_periodo is None:
            return {
                "ok": True,
                "periodos": [],
                "mensaje": "Columna de período no encontrada — se procesará sin validación.",
            }

        # Filtrar solo SIF82/TES82
        col_tipo = next((c for c in ["Tipo", "tipo", "TIPO"] if c in df.columns), None)
        if col_tipo:
            df = df.filter(df[col_tipo].is_in(["SIF82", "TES82"]))

        periodos = sorted(df[col_periodo].drop_nulls().unique().to_list())
        periodos = [p for p in periodos if p and str(p).strip()]

        if len(periodos) > 1:
            return {
                "ok": False,
                "periodos": periodos,
                "mensaje": (
                    f"El archivo contiene {len(periodos)} períodos diferentes: "
                    f"{', '.join(periodos)}. "
                    f"Sube un archivo con datos de un solo período contable."
                ),
            }

        return {"ok": True, "periodos": periodos, "mensaje": "Archivo válido."}

    except Exception as e:
        return {"ok": False, "periodos": [], "mensaje": f"Error al leer el archivo: {e}"}

    finally:
        try:
            _os.unlink(tmp.name)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 1 — Subir archivo (responde inmediato, procesa en background)
# ══════════════════════════════════════════════════════════════════
@router.post("/upload-and-reconcile/", tags=["Conciliación"])
async def upload_and_reconcile(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    modo: Literal["un_periodo", "multi_periodo"] = Query(default="un_periodo"),
):
    """
    Sube el archivo y lanza el proceso en background.
    Responde inmediatamente con status 202.
    Consulta /estado/ para ver el progreso.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos .xlsx o .xls")

    estado_actual = _leer_estado()
    if estado_actual["fase"] in ("cargando", "procesando"):
        raise HTTPException(409, "Ya hay un proceso en curso. Consulta /estado/")

    os.makedirs("data_samples", exist_ok=True)
    temp_path = f"data_samples/temp_{file.filename}"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    id_lote = int(time.time())  # único por ejecución — nunca sobreescribe datos anteriores
    _escribir_estado(
        {
            "fase": "iniciando",
            "mensaje": "Archivo recibido, iniciando...",
            "conciliados": 0,
            "pendientes": 0,
            "tasa": 0.0,
            "reporte": None,
        }
    )
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
# ENDPOINT 2b — Cancelar proceso en curso
# ══════════════════════════════════════════════════════════════════
@router.post("/cancelar/", tags=["Conciliación"])
async def cancelar():
    """
    Marca el proceso como cancelado. El hilo de background detecta la señal
    y se detiene en el próximo punto de control.
    """
    estado_actual = _leer_estado()
    if estado_actual.get("fase") not in ("cargando", "procesando", "iniciando"):
        return {"status": "noop", "mensaje": "No hay proceso activo para cancelar."}

    _escribir_estado({**estado_actual, "fase": "cancelado", "mensaje": "Cancelado por el usuario."})
    return {"status": "ok", "mensaje": "Señal de cancelación enviada."}


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 2c — Programar ejecución nocturna
# ══════════════════════════════════════════════════════════════════
@router.post("/programar/", tags=["Conciliación"])
async def programar_ejecucion(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    hora: str = Query(..., description="HH:MM – hora de ejecución"),
    fecha: str = Query(default="", description="YYYY-MM-DD – vacío = hoy"),
    f2_timeout: int = Query(default=2),
    f3_timeout: int = Query(default=10),
    f4_timeout: int = Query(default=30),
    max_depth: int = Query(default=5),
):
    """Guarda el archivo y registra la ejecución programada para la hora indicada."""
    import json as _json
    from datetime import datetime as _dt, date as _date

    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo .xlsx o .xls")

    # Validar hora
    try:
        _dt.strptime(hora, "%H:%M")
    except ValueError:
        raise HTTPException(400, "Formato de hora inválido. Usa HH:MM")

    fecha_prog = fecha if fecha else _date.today().isoformat()

    # Guardar archivo en carpeta temporal permanente
    os.makedirs("data_samples/programados", exist_ok=True)
    ts = int(time.time())
    archivo_path = f"data_samples/programados/{ts}_{file.filename}"
    with open(archivo_path, "wb") as f:
        import shutil as _sh

        _sh.copyfileobj(file.file, f)

    config_json = _json.dumps(
        {
            "f2_timeout": f2_timeout,
            "f3_timeout": f3_timeout,
            "f4_timeout": f4_timeout,
            "max_depth": max_depth,
        }
    )

    creado_en = _dt.now().strftime("%d/%m/%Y %H:%M")

    with engine.begin() as con:
        result = con.execute(
            _sql("""
            INSERT INTO ejecucion_programada
                (fecha_programada, hora_programada, archivo_path, archivo_nombre,
                 config_json, estado, creado_en)
            VALUES (:fecha, :hora, :path, :nombre, :cfg, 'PENDIENTE', :creado)
        """),
            {
                "fecha": fecha_prog,
                "hora": hora,
                "path": archivo_path,
                "nombre": file.filename,
                "cfg": config_json,
                "creado": creado_en,
            },
        )
        prog_id = result.inserted_primary_key[0] if IS_POSTGRES else result.lastrowid

    # Iniciar el scheduler en background si no está corriendo
    background_tasks.add_task(_scheduler_tick)

    return {
        "status": "programado",
        "id": prog_id,
        "archivo": file.filename,
        "fecha": fecha_prog,
        "hora": hora,
        "mensaje": f"Ejecución programada para el {fecha_prog} a las {hora}",
    }


@router.get("/programadas/", tags=["Conciliación"])
async def listar_programadas():
    """Lista todas las ejecuciones programadas pendientes y recientes."""
    with engine.connect() as con:
        rows = con.execute(_sql("""
            SELECT id, fecha_programada, hora_programada, archivo_nombre,
                   estado, creado_en, ejecutado_en
            FROM ejecucion_programada
            ORDER BY fecha_programada DESC, hora_programada DESC
            LIMIT 50
        """)).fetchall()

    return {
        "programadas": [
            {
                "id": r[0],
                "fecha": r[1],
                "hora": r[2],
                "archivo": r[3],
                "estado": r[4],
                "creado_en": r[5],
                "ejecutado_en": r[6],
            }
            for r in rows
        ]
    }


@router.delete("/programadas/{prog_id}", tags=["Conciliación"])
async def cancelar_programada(prog_id: int):
    """Cancela una ejecución programada pendiente."""
    with engine.begin() as con:
        result = con.execute(
            _sql("""
            UPDATE ejecucion_programada SET estado='CANCELADO'
            WHERE id=:pid AND estado='PENDIENTE'
        """),
            {"pid": prog_id},
        )
        affected = result.rowcount

    if affected == 0:
        raise HTTPException(404, "Ejecución no encontrada o ya procesada.")

    return {"status": "ok", "mensaje": "Ejecución programada cancelada."}


@router.get("/programadas/proxima/", tags=["Conciliación"])
async def proxima_programada():
    """
    Retorna la próxima ejecución pendiente con el tiempo restante en segundos.
    Útil para que el frontend muestre una cuenta regresiva.
    """
    from datetime import datetime as _dt

    with engine.connect() as con:
        row = con.execute(_sql("""
            SELECT id, fecha_programada, hora_programada, archivo_nombre, creado_en
            FROM ejecucion_programada
            WHERE estado = 'PENDIENTE'
            ORDER BY fecha_programada ASC, hora_programada ASC
            LIMIT 1
        """)).fetchone()

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
            "id": prog_id,
            "fecha": fecha_str,
            "hora": hora_str,
            "archivo": archivo,
            "creado_en": creado_en,
            "segundos_restantes": segundos_restantes,
            "ya_paso": ya_paso,
        }
    }


def _scheduler_tick():
    """
    Scheduler robusto de ejecuciones programadas.
    - Arranca un único hilo daemon al iniciar el servidor
    - Verifica cada 30 segundos si hay ejecuciones que ejecutar
    - Al arrancar, recupera las que quedaron en EJECUTANDO (reinicio del servidor)
    - Comparación correcta: fecha+hora como datetime completo
    - Cada ejecución corre en su propio hilo para no bloquear el scheduler
    """
    import json as _json
    from datetime import datetime as _dt
    import threading as _th

    def _ejecutar_programada(prog_id: int, archivo_path: str, config_json: str):
        """Ejecuta una conciliación programada en un hilo separado."""
        try:
            _marcar_programada(prog_id, "EJECUTANDO")
            id_lote = int(time.time())
            print(f"🕐 Scheduler: iniciando prog_id={prog_id} → lote {id_lote}")
            _procesar_en_background(archivo_path, id_lote)
            _marcar_programada(prog_id, "COMPLETADO")
            print(f"✅ Scheduler: prog_id={prog_id} completado")
        except Exception as e:
            print(f"❌ Scheduler: prog_id={prog_id} error: {e}")
            _marcar_programada(prog_id, "ERROR")

    def _run():
        print("🕐 Scheduler de ejecuciones programadas iniciado.")

        # Al arrancar: recuperar las que quedaron en EJECUTANDO por reinicio
        try:
            with engine.begin() as con:
                result = con.execute(_sql("""
                    UPDATE ejecucion_programada
                    SET estado = 'PENDIENTE'
                    WHERE estado = 'EJECUTANDO'
                """))
                recuperadas = result.rowcount

            if recuperadas:
                print(f"🔄 Scheduler: {recuperadas} ejecución(es) recuperada(s) tras reinicio")

        except Exception as e:
            print(f"⚠️ Scheduler: error al recuperar pendientes: {e}")

        while True:
            try:
                ahora = _dt.now()

                with engine.connect() as con:
                    pendientes = con.execute(_sql("""
                        SELECT id, archivo_path, config_json,
                               fecha_programada, hora_programada
                        FROM ejecucion_programada
                        WHERE estado = 'PENDIENTE'
                        ORDER BY fecha_programada ASC, hora_programada ASC
                    """)).fetchall()

                for prog_id, archivo_path, config_json, fecha_str, hora_str in pendientes:
                    # Construir datetime programado y comparar con ahora
                    try:
                        dt_prog = _dt.strptime(f"{fecha_str} {hora_str}", "%Y-%m-%d %H:%M")
                    except ValueError:
                        print(f"⚠️ Scheduler: formato de fecha/hora inválido en prog_id={prog_id}")
                        _marcar_programada(prog_id, "ERROR")
                        continue

                    # Solo ejecutar si ya llegó o pasó el momento programado
                    if ahora < dt_prog:
                        minutos_restantes = int((dt_prog - ahora).total_seconds() / 60)
                        print(
                            f"⏳ Scheduler: prog_id={prog_id} programado en {minutos_restantes} min "
                            f"({fecha_str} {hora_str})"
                        )
                        continue

                    # Verificar que el archivo existe
                    if not os.path.exists(archivo_path):
                        print(
                            f"❌ Scheduler: archivo no encontrado para prog_id={prog_id}: {archivo_path}"
                        )
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
                    print(f"🚀 Scheduler: lanzando prog_id={prog_id} ({fecha_str} {hora_str})")

            except Exception as e:
                print(f"❌ Scheduler tick error: {e}")

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

    with engine.begin() as con:
        con.execute(
            _sql("""
            UPDATE ejecucion_programada
            SET estado=:estado, ejecutado_en=:ts
            WHERE id=:pid
        """),
            {"estado": estado, "ts": _dt.now().strftime("%d/%m/%Y %H:%M"), "pid": prog_id},
        )


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 3 — Acumulación multi-período
# ══════════════════════════════════════════════════════════════════
@router.post("/upload-multi/", tags=["Multi-período"])
async def upload_multi(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    accion: Literal["agregar", "conciliar", "limpiar"] = Query(default="agregar"),
):
    if accion == "limpiar":
        db.limpiar_transacciones_lote(2)
        return {"status": "ok", "mensaje": "Acumulación limpiada."}

    if not file.filename.endswith((".xlsx", ".xls")):
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
                (
                    r["descripcion"],
                    str(r["cuenta_contable"]),
                    r["monto_centavos"],
                    r["n_diario"],
                    str(r["localidad"]),
                    str(r["periodo"]),
                    str(r["tipo"]),
                    2,
                )
                for r in df.to_dicts()
            ]
            del df
            gc.collect()

            for i in range(0, len(regs), BATCH_SIZE):
                db.insertar_transacciones(regs[i : i + BATCH_SIZE])

            total = db.contar_pendientes_lote(cuenta, 2)
            return {"status": "acumulado", "archivo": file.filename, "total_acumulado": total}
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    # accion == "conciliar"
    _escribir_estado(
        {
            "fase": "iniciando",
            "mensaje": "Iniciando conciliación multi-período...",
            "conciliados": 0,
            "pendientes": 0,
            "tasa": 0.0,
            "reporte": None,
        }
    )
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
    """
    Descarga un reporte Excel.
    - Busca el archivo por nombre en la carpeta local 'reportes/'
    - Si no existe (p.ej. DB remota en Railway pero servidor local sin el archivo),
      lo regenera desde la DB usando el id_lote y cuenta del historial.
    - Portable: la ruta guardada en DB es solo el nombre del archivo.
    """
    # Normalizar: aceptar nombre solo o ruta completa
    nombre = os.path.basename(filename)
    ruta = os.path.join("reportes", nombre)

    # Si no existe localmente, intentar regenerar desde la DB
    if not os.path.exists(ruta):
        try:
            with engine.connect() as con:
                row = con.execute(
                    _sql("""
                    SELECT cuenta, id_lote FROM historial_ejecucion
                    WHERE ruta_reporte = :n OR ruta_reporte LIKE :nl
                    ORDER BY id DESC LIMIT 1
                """),
                    {"n": nombre, "nl": f"%{nombre}"},
                ).fetchone()

            if row:
                cuenta_reg, id_lote_reg = row
                nombre_gen = reporter.generar_excel_desde_db(db, cuenta_reg, id_lote_reg)
                ruta = os.path.join("reportes", nombre_gen)
        except Exception as _er:
            print(f"⚠️ No se pudo regenerar el reporte: {_er}")

    if not os.path.exists(ruta):
        raise HTTPException(404, f"Reporte no encontrado y no se pudo regenerar: {nombre}")

    return FileResponse(
        path=ruta,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=nombre,
    )


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 5b — Reporte PDF profesional generado desde la DB
# ══════════════════════════════════════════════════════════════════
@router.get("/download-report-pdf/{filename}", tags=["Reportes"])
async def download_report_pdf(filename: str):
    """Genera un PDF profesional con KPIs, resumen por fase y muestra de transacciones."""
    from datetime import datetime as _dt

    nombre_xlsx = os.path.basename(filename)
    ruta_xlsx = os.path.join("reportes", nombre_xlsx)

    # Si no existe localmente, regenerar desde la DB
    if not os.path.exists(ruta_xlsx):
        try:
            with engine.connect() as con:
                row = con.execute(
                    _sql("""
                    SELECT cuenta, id_lote FROM historial_ejecucion
                    WHERE ruta_reporte = :n OR ruta_reporte LIKE :nl
                    ORDER BY id DESC LIMIT 1
                """),
                    {"n": nombre_xlsx, "nl": f"%{nombre_xlsx}"},
                ).fetchone()

            if row:
                cuenta_reg, id_lote_reg = row
                nombre_gen = reporter.generar_excel_desde_db(db, cuenta_reg, id_lote_reg)
                ruta_xlsx = os.path.join("reportes", nombre_gen)
        except Exception as _ep:
            print(f"⚠️ No se pudo regenerar Excel para PDF: {_ep}")

    if not os.path.exists(ruta_xlsx):
        raise HTTPException(404, f"Reporte no encontrado: {nombre_xlsx}")

    pdf_name = nombre_xlsx.replace(".xlsx", ".pdf").replace(".xls", ".pdf")
    ruta_pdf = os.path.join("reportes", pdf_name)

    necesita_generar = not os.path.exists(ruta_pdf) or os.path.getmtime(
        ruta_xlsx
    ) > os.path.getmtime(ruta_pdf)

    if necesita_generar:
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib import colors
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate,
                Paragraph,
                Spacer,
                Table,
                TableStyle,
                HRFlowable,
                PageBreak,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

            # ── Colores corporativos ──────────────────────────────────────────
            AZUL_OSCURO = colors.HexColor("#1e3a5f")
            AZUL_MEDIO = colors.HexColor("#2563eb")
            AZUL_CLARO = colors.HexColor("#dbeafe")
            VERDE = colors.HexColor("#16a34a")
            VERDE_CLARO = colors.HexColor("#dcfce7")
            ROJO = colors.HexColor("#dc2626")
            ROJO_CLARO = colors.HexColor("#fee2e2")
            GRIS_CLARO = colors.HexColor("#f8fafc")
            GRIS_BORDE = colors.HexColor("#e2e8f0")
            BLANCO = colors.white

            # ── Estilos ───────────────────────────────────────────────────────
            styles = getSampleStyleSheet()
            st_titulo = ParagraphStyle(
                "titulo",
                fontName="Helvetica-Bold",
                fontSize=22,
                textColor=BLANCO,
                alignment=TA_CENTER,
                spaceAfter=4,
            )
            st_subtitulo = ParagraphStyle(
                "subtitulo",
                fontName="Helvetica",
                fontSize=11,
                textColor=colors.HexColor("#93c5fd"),
                alignment=TA_CENTER,
            )
            st_seccion = ParagraphStyle(
                "seccion",
                fontName="Helvetica-Bold",
                fontSize=12,
                textColor=AZUL_OSCURO,
                spaceBefore=14,
                spaceAfter=6,
            )
            st_normal = ParagraphStyle(
                "normal",
                fontName="Helvetica",
                fontSize=9,
                textColor=colors.HexColor("#374151"),
                leading=13,
            )
            st_pie = ParagraphStyle(
                "pie",
                fontName="Helvetica",
                fontSize=7,
                textColor=colors.HexColor("#9ca3af"),
                alignment=TA_CENTER,
            )
            st_kpi_val = ParagraphStyle(
                "kpi_val",
                fontName="Helvetica-Bold",
                fontSize=20,
                textColor=AZUL_OSCURO,
                alignment=TA_CENTER,
            )
            st_kpi_lbl = ParagraphStyle(
                "kpi_lbl",
                fontName="Helvetica",
                fontSize=8,
                textColor=colors.HexColor("#6b7280"),
                alignment=TA_CENTER,
            )

            # ── Leer datos de la DB ───────────────────────────────────────────
            with engine.connect() as con:
                # Buscar el lote más reciente que coincida con el reporte
                row_h = con.execute(
                    _sql("""
                    SELECT h.id_lote, h.cuenta, h.total, h.conciliados, h.pendientes,
                           h.tasa, h.periodo, h.fecha
                    FROM historial_ejecucion h
                    WHERE h.ruta_reporte LIKE :pat
                    ORDER BY h.id DESC LIMIT 1
                """),
                    {"pat": f"%{nombre_xlsx.replace('.xlsx','')}%"},
                ).fetchone()

                if row_h:
                    id_lote, cuenta, total, conciliados, pendientes, tasa, periodo, fecha_ej = row_h
                else:
                    row_t = con.execute(_sql("""
                        SELECT id_lote, cuenta_contable,
                               COUNT(*) as total,
                               SUM(CASE WHEN estado_tx='CONCILIADO' THEN 1 ELSE 0 END),
                               SUM(CASE WHEN estado_tx='PENDIENTE'  THEN 1 ELSE 0 END)
                        FROM transaccion GROUP BY id_lote ORDER BY id_lote DESC LIMIT 1
                    """)).fetchone()
                    if not row_t:
                        raise ValueError("No hay datos en la base de datos.")
                    id_lote, cuenta, total, conciliados, pendientes = row_t
                    tasa = round(conciliados / total * 100, 2) if total else 0
                    periodo, fecha_ej = "", _dt.now().strftime("%d/%m/%Y %H:%M")

                fases_raw = con.execute(
                    _sql("""
                    SELECT
                        CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
                        COUNT(t.id_transaccion) AS n
                    FROM transaccion t
                    JOIN conciliacion c ON ABS(t.id_conciliacion) = c.id_conciliacion
                    WHERE t.id_lote = :lote AND t.estado_tx = 'CONCILIADO'
                    GROUP BY fase ORDER BY fase
                """),
                    {"lote": id_lote},
                ).fetchall()
                fases = {r[0]: r[1] for r in fases_raw}

                muestra_conci = con.execute(
                    _sql("""
                    SELECT t.tipo, t.periodo, t.descripcion, t.localidad,
                           ROUND(CAST(t.monto_centavos AS REAL)/100, 2),
                           COALESCE(c.fase_origen,'?')
                    FROM transaccion t
                    JOIN conciliacion c ON ABS(t.id_conciliacion) = c.id_conciliacion
                    WHERE t.id_lote = :lote AND t.estado_tx = 'CONCILIADO'
                    ORDER BY c.fase_origen, ABS(t.id_conciliacion)
                    LIMIT 50
                """),
                    {"lote": id_lote},
                ).fetchall()

                muestra_pend = con.execute(
                    _sql("""
                    SELECT tipo, periodo, descripcion, localidad,
                           ROUND(CAST(monto_centavos AS REAL)/100, 2)
                    FROM transaccion
                    WHERE id_lote = :lote AND estado_tx = 'PENDIENTE'
                    ORDER BY ABS(monto_centavos) DESC
                    LIMIT 30
                """),
                    {"lote": id_lote},
                ).fetchall()

            pendientes_real = total - conciliados
            fecha_gen = _dt.now().strftime("%d/%m/%Y %H:%M")

            # ── Construir PDF ─────────────────────────────────────────────────
            doc = SimpleDocTemplate(
                ruta_pdf,
                pagesize=A4,
                leftMargin=1.8 * cm,
                rightMargin=1.8 * cm,
                topMargin=1.5 * cm,
                bottomMargin=1.5 * cm,
            )

            page_w = A4[0] - 3.6 * cm
            elems = []

            # ── PORTADA ───────────────────────────────────────────────────────
            portada_data = [
                [
                    Paragraph("REPORTE DE CONCILIACIÓN CONTABLE", st_titulo),
                ]
            ]
            portada = Table(portada_data, colWidths=[page_w])
            portada.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), AZUL_OSCURO),
                        ("TOPPADDING", (0, 0), (-1, -1), 22),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ("LEFTPADDING", (0, 0), (-1, -1), 16),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                        ("ROUNDEDCORNERS", (0, 0), (-1, -1), [8, 8, 8, 8]),
                    ]
                )
            )
            elems.append(portada)

            sub_data = [
                [
                    Paragraph(
                        f"Cuenta: {cuenta}  |  Período: {periodo or '—'}  |  Generado: {fecha_gen}",
                        st_subtitulo,
                    )
                ]
            ]
            sub_t = Table(sub_data, colWidths=[page_w])
            sub_t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e40af")),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ]
                )
            )
            elems.append(sub_t)
            elems.append(Spacer(1, 18))

            # ── KPIs ──────────────────────────────────────────────────────────
            elems.append(Paragraph("Resumen Ejecutivo", st_seccion))
            elems.append(HRFlowable(width=page_w, thickness=1.5, color=AZUL_MEDIO, spaceAfter=10))

            def kpi_cell(valor, label, bg, fg_val=AZUL_OSCURO):
                return [
                    Paragraph(
                        str(valor),
                        ParagraphStyle(
                            "kv",
                            fontName="Helvetica-Bold",
                            fontSize=18,
                            textColor=fg_val,
                            alignment=TA_CENTER,
                        ),
                    ),
                    Paragraph(
                        label,
                        ParagraphStyle(
                            "kl",
                            fontName="Helvetica",
                            fontSize=8,
                            textColor=colors.HexColor("#6b7280"),
                            alignment=TA_CENTER,
                        ),
                    ),
                ]

            kpi_w = page_w / 4 - 4
            kpi_data = [
                [
                    kpi_cell(f"{total:,}", "Total Registros", GRIS_CLARO),
                    kpi_cell(f"{conciliados:,}", "Conciliados", VERDE_CLARO, VERDE),
                    kpi_cell(f"{pendientes_real:,}", "Pendientes", ROJO_CLARO, ROJO),
                    kpi_cell(f"{tasa:.1f}%", "Efectividad", AZUL_CLARO, AZUL_MEDIO),
                ]
            ]
            kpi_t = Table(kpi_data, colWidths=[kpi_w] * 4, rowHeights=[None])
            kpi_t.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (0, -1), GRIS_CLARO),
                        ("BACKGROUND", (1, 0), (1, -1), VERDE_CLARO),
                        ("BACKGROUND", (2, 0), (2, -1), ROJO_CLARO),
                        ("BACKGROUND", (3, 0), (3, -1), AZUL_CLARO),
                        ("BOX", (0, 0), (0, -1), 1, GRIS_BORDE),
                        ("BOX", (1, 0), (1, -1), 1, colors.HexColor("#86efac")),
                        ("BOX", (2, 0), (2, -1), 1, colors.HexColor("#fca5a5")),
                        ("BOX", (3, 0), (3, -1), 1, colors.HexColor("#93c5fd")),
                        ("TOPPADDING", (0, 0), (-1, -1), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ]
                )
            )
            elems.append(kpi_t)
            elems.append(Spacer(1, 18))

            # ── RESUMEN POR FASE ──────────────────────────────────────────────
            elems.append(Paragraph("Desglose por Fase de Conciliación", st_seccion))
            elems.append(HRFlowable(width=page_w, thickness=1.5, color=AZUL_MEDIO, spaceAfter=10))

            fase_descripciones = {
                "F1": "Fast-Pass — Coincidencias exactas 1:1 (n_diario + localidad + monto)",
                "F2": "Subset Sum — Grupos N:N con suma cero (mismo n_diario y localidad)",
                "F3": "Tolerancia — Grupos con diferencia ≤ 5 centavos",
                "F4": "Localidad — Parejas exactas por monto + localidad (sin n_diario)",
                "F5": "Monto Puro — Parejas exactas solo por monto (último recurso 1:1)",
                "F6": "Subset Sum Global — N positivos → 1 negativo (programación dinámica)",
                "F7": "Final Cleaning — 1 positivo → N negativos (programación dinámica)",
                "F7b": "Final Cleaning B — Positivos restantes → N negativos",
            }

            fase_hdr = [
                Paragraph(
                    "Fase",
                    ParagraphStyle(
                        "fh",
                        fontName="Helvetica-Bold",
                        fontSize=9,
                        textColor=BLANCO,
                        alignment=TA_CENTER,
                    ),
                ),
                Paragraph(
                    "Descripción",
                    ParagraphStyle("fh", fontName="Helvetica-Bold", fontSize=9, textColor=BLANCO),
                ),
                Paragraph(
                    "Conciliados",
                    ParagraphStyle(
                        "fh",
                        fontName="Helvetica-Bold",
                        fontSize=9,
                        textColor=BLANCO,
                        alignment=TA_RIGHT,
                    ),
                ),
                Paragraph(
                    "% del Total",
                    ParagraphStyle(
                        "fh",
                        fontName="Helvetica-Bold",
                        fontSize=9,
                        textColor=BLANCO,
                        alignment=TA_RIGHT,
                    ),
                ),
                Paragraph(
                    "% Conciliados",
                    ParagraphStyle(
                        "fh",
                        fontName="Helvetica-Bold",
                        fontSize=9,
                        textColor=BLANCO,
                        alignment=TA_RIGHT,
                    ),
                ),
            ]

            fase_rows = [fase_hdr]
            for fk in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F7b"]:
                n = fases.get(fk, 0)
                if n == 0:
                    continue
                pct_total = round(n / total * 100, 1) if total else 0
                pct_conci = round(n / conciliados * 100, 1) if conciliados else 0
                fase_rows.append(
                    [
                        Paragraph(
                            fk,
                            ParagraphStyle(
                                "fc",
                                fontName="Helvetica-Bold",
                                fontSize=9,
                                textColor=AZUL_OSCURO,
                                alignment=TA_CENTER,
                            ),
                        ),
                        Paragraph(fase_descripciones.get(fk, fk), st_normal),
                        Paragraph(
                            f"{n:,}",
                            ParagraphStyle(
                                "fn", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT
                            ),
                        ),
                        Paragraph(
                            f"{pct_total}%",
                            ParagraphStyle(
                                "fn", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT
                            ),
                        ),
                        Paragraph(
                            f"{pct_conci}%",
                            ParagraphStyle(
                                "fn", fontName="Helvetica", fontSize=9, alignment=TA_RIGHT
                            ),
                        ),
                    ]
                )

            if len(fase_rows) > 1:
                fase_t = Table(
                    fase_rows, colWidths=[1.2 * cm, page_w - 8.2 * cm, 2.5 * cm, 2.2 * cm, 2.3 * cm]
                )
                fase_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), AZUL_OSCURO),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANCO, GRIS_CLARO]),
                    ("GRID", (0, 0), (-1, -1), 0.4, GRIS_BORDE),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
                fase_t.setStyle(TableStyle(fase_style))
                elems.append(fase_t)

            elems.append(Spacer(1, 18))

            # ── MUESTRA CONCILIADOS ───────────────────────────────────────────
            if muestra_conci:
                elems.append(
                    Paragraph(
                        f"Muestra de Transacciones Conciliadas (primeras {len(muestra_conci)})",
                        st_seccion,
                    )
                )
                elems.append(HRFlowable(width=page_w, thickness=1.5, color=VERDE, spaceAfter=10))

                mc_hdr = ["Tipo", "Período", "Descripción", "Localidad", "Monto (COP)", "Fase"]
                mc_hdr_row = [
                    Paragraph(
                        h,
                        ParagraphStyle(
                            "mh",
                            fontName="Helvetica-Bold",
                            fontSize=8,
                            textColor=BLANCO,
                            alignment=TA_CENTER,
                        ),
                    )
                    for h in mc_hdr
                ]
                mc_rows = [mc_hdr_row]

                for r in muestra_conci:
                    tipo, per, desc, loc, monto, fase = r
                    monto_fmt = f"{monto:,.2f}" if monto else "0.00"
                    color_monto = ROJO if (monto or 0) < 0 else VERDE
                    mc_rows.append(
                        [
                            Paragraph(str(tipo or ""), st_normal),
                            Paragraph(str(per or ""), st_normal),
                            Paragraph(str(desc or "")[:60], st_normal),
                            Paragraph(str(loc or ""), st_normal),
                            Paragraph(
                                monto_fmt,
                                ParagraphStyle(
                                    "mn",
                                    fontName="Helvetica",
                                    fontSize=8,
                                    textColor=color_monto,
                                    alignment=TA_RIGHT,
                                ),
                            ),
                            Paragraph(
                                str(fase or ""),
                                ParagraphStyle(
                                    "mf",
                                    fontName="Helvetica-Bold",
                                    fontSize=8,
                                    textColor=AZUL_MEDIO,
                                    alignment=TA_CENTER,
                                ),
                            ),
                        ]
                    )

                mc_t = Table(
                    mc_rows,
                    colWidths=[1.2 * cm, 2 * cm, page_w - 10.4 * cm, 2.5 * cm, 2.7 * cm, 1 * cm],
                )
                mc_t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#166534")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANCO, VERDE_CLARO]),
                            ("GRID", (0, 0), (-1, -1), 0.3, GRIS_BORDE),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]
                    )
                )
                elems.append(mc_t)
                elems.append(Spacer(1, 18))

            # ── MUESTRA PENDIENTES ────────────────────────────────────────────
            if muestra_pend:
                elems.append(
                    Paragraph(
                        f"Muestra de Transacciones Pendientes (top {len(muestra_pend)} por monto)",
                        st_seccion,
                    )
                )
                elems.append(HRFlowable(width=page_w, thickness=1.5, color=ROJO, spaceAfter=10))

                mp_hdr = ["Tipo", "Período", "Descripción", "Localidad", "Monto (COP)"]
                mp_hdr_row = [
                    Paragraph(
                        h,
                        ParagraphStyle(
                            "ph",
                            fontName="Helvetica-Bold",
                            fontSize=8,
                            textColor=BLANCO,
                            alignment=TA_CENTER,
                        ),
                    )
                    for h in mp_hdr
                ]
                mp_rows = [mp_hdr_row]

                for r in muestra_pend:
                    tipo, per, desc, loc, monto = r
                    monto_fmt = f"{monto:,.2f}" if monto else "0.00"
                    color_monto = ROJO if (monto or 0) < 0 else VERDE
                    mp_rows.append(
                        [
                            Paragraph(str(tipo or ""), st_normal),
                            Paragraph(str(per or ""), st_normal),
                            Paragraph(str(desc or "")[:60], st_normal),
                            Paragraph(str(loc or ""), st_normal),
                            Paragraph(
                                monto_fmt,
                                ParagraphStyle(
                                    "pm",
                                    fontName="Helvetica",
                                    fontSize=8,
                                    textColor=color_monto,
                                    alignment=TA_RIGHT,
                                ),
                            ),
                        ]
                    )

                mp_t = Table(
                    mp_rows, colWidths=[1.2 * cm, 2 * cm, page_w - 8.9 * cm, 2.5 * cm, 2.7 * cm]
                )
                mp_t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#991b1b")),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [BLANCO, ROJO_CLARO]),
                            ("GRID", (0, 0), (-1, -1), 0.3, GRIS_BORDE),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ]
                    )
                )
                elems.append(mp_t)
                elems.append(Spacer(1, 14))

            # ── PIE DE PÁGINA ─────────────────────────────────────────────────
            elems.append(HRFlowable(width=page_w, thickness=0.5, color=GRIS_BORDE))
            elems.append(Spacer(1, 6))
            elems.append(
                Paragraph(
                    f"Conciliador Pro  ·  Generado el {fecha_gen}  ·  Archivo: {filename}  ·  "
                    f"Total procesado: {total:,} registros",
                    st_pie,
                )
            )

            doc.build(elems)

        except ImportError as e:
            print(f"❌ PDF ImportError: {e}")
            raise HTTPException(
                500, f"Dependencia faltante: {e}. Ejecuta: pip install reportlab openpyxl"
            )

        except Exception as e:
            import traceback as _tb

            print(f"❌ PDF Error: {e}")
            print(_tb.format_exc())
            raise HTTPException(500, f"Error generando PDF: {e}")

    return FileResponse(path=ruta_pdf, media_type="application/pdf", filename=pdf_name)


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 6 — Listar transacciones conciliadas o pendientes
# ══════════════════════════════════════════════════════════════════
@router.get("/transacciones/", tags=["Datos"])
async def listar_transacciones(
    estado: str = Query(..., description="CONCILIADO o PENDIENTE"),
    cuenta: str = Query(..., description="Número de cuenta contable"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, le=500),
):
    """Retorna registros paginados filtrados por estado y cuenta."""
    if estado not in ("CONCILIADO", "PENDIENTE"):
        raise HTTPException(400, "estado debe ser CONCILIADO o PENDIENTE")

    offset = (page - 1) * limit

    with engine.connect() as con:
        filas = con.execute(
            _sql("""
            SELECT  t.id_transaccion,
                    t.tipo,
                    t.periodo,
                    t.descripcion,
                    t.localidad,
                    ROUND(CAST(t.monto_centavos AS REAL) / 100, 2) AS monto,
                    t.n_diario,
                    t.id_conciliacion,
                    COALESCE(c.fase_origen, NULL) AS fase_origen
            FROM    transaccion t
            LEFT JOIN conciliacion c
                   ON ABS(t.id_conciliacion) = c.id_conciliacion
            WHERE   t.estado_tx      = :estado
              AND   t.cuenta_contable = :cuenta
            ORDER BY COALESCE(c.fase_origen, 'ZZ'),
                     ABS(t.id_conciliacion),
                     t.id_transaccion
            LIMIT :limit OFFSET :offset
        """),
            {"estado": estado, "cuenta": cuenta, "limit": limit, "offset": offset},
        ).fetchall()

        total = (
            con.execute(
                _sql("""
            SELECT COUNT(*)
            FROM   transaccion
            WHERE  estado_tx = :estado AND cuenta_contable = :cuenta
        """),
                {"estado": estado, "cuenta": cuenta},
            ).scalar()
            or 0
        )

    return {
        "items": [
            {
                "id": f[0],
                "tipo": f[1],
                "periodo": f[2],
                "descripcion": f[3],
                "localidad": f[4],
                "monto": f[5],
                "n_diario": f[6],
                "grupo": f[7],  # id_conciliacion
                "fase": f[8],  # F1 / F2 / F3 / F4 / F5 / null
            }
            for f in filas
        ],
        "total": total,
        "page": page,
        "pages": max(1, (total + limit - 1) // limit),
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
    _escribir_estado(
        {
            **_leer_estado(),
            "fase": "procesando",
            "mensaje": "Infiriendo fases de conciliaciones antiguas...",
        }
    )
    t0 = time.time()

    with engine.connect() as con:
        grupos_sin_fase = [r[0] for r in con.execute(_sql("""
                SELECT id_conciliacion FROM conciliacion
                WHERE fase_origen = 'F?' OR fase_origen IS NULL
            """)).fetchall()]

    if not grupos_sin_fase:
        _escribir_estado(
            {
                **_leer_estado(),
                "fase": "listo",
                "mensaje": "Todas las conciliaciones ya tienen fase asignada.",
            }
        )
        return

    actualizados = {"F1": 0, "F2": 0, "F3": 0, "F4": 0, "F5": 0}
    LOTE = 500

    for i in range(0, len(grupos_sin_fase), LOTE):
        batch_ids = grupos_sin_fase[i : i + LOTE]

        with engine.connect() as con:
            filas = con.execute(
                _sql(f"""
                SELECT id_conciliacion, n_diario, localidad, monto_centavos
                FROM   transaccion
                WHERE  id_conciliacion IN ({','.join(':id'+str(j) for j in range(len(batch_ids)))})
                ORDER  BY id_conciliacion
                """),
                {f"id{j}": v for j, v in enumerate(batch_ids)},
            ).fetchall()

        # Agrupar por id_conciliacion
        grupos = defaultdict(list)
        for gid, nd, loc, monto in filas:
            grupos[gid].append({"n_diario": nd, "localidad": loc, "monto": monto})

        updates = []
        for gid, txs in grupos.items():
            n = len(txs)
            suma = sum(t["monto"] for t in txs)
            mismo_ndiario = len(set(t["n_diario"] for t in txs)) == 1
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

        with engine.begin() as con:
            for fase_val, gid_val in updates:
                con.execute(
                    _sql("""
                    UPDATE conciliacion SET fase_origen = :fase WHERE id_conciliacion = :gid
                """),
                    {"fase": fase_val, "gid": gid_val},
                )

        if i % 5000 == 0:
            pct = min(100, int(i / len(grupos_sin_fase) * 100))
            _escribir_estado(
                {
                    **_leer_estado(),
                    "mensaje": f"Infiriendo fases... {pct}% ({i:,}/{len(grupos_sin_fase):,} grupos)",
                }
            )

    resumen = ", ".join(f"{f}:{v:,}" for f, v in actualizados.items() if v > 0)
    _escribir_estado(
        {
            **_leer_estado(),
            "fase": "listo",
            "mensaje": f"Fases inferidas en {time.time()-t0:.1f}s — {resumen}",
        }
    )
    print(f"✅ Fases inferidas: {resumen}")


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 8 — Historial de ejecuciones desde la DB
# Fuente de verdad universal: funciona en cualquier IP/origen
# ══════════════════════════════════════════════════════════════════
@router.get("/historial/", tags=["Datos"])
async def obtener_historial():
    """
    Retorna todas las ejecuciones desde historial_ejecucion.
    Fuente de verdad universal — funciona desde cualquier IP/dispositivo.
    """
    try:
        with engine.connect() as con:
            rows = con.execute(_sql("""
                SELECT id, fecha, cuenta, total, conciliados, pendientes,
                       tasa, periodo, mes, anio, ruta_reporte, id_lote,
                       COALESCE(estado, 'COMPLETADO') as estado
                FROM   historial_ejecucion
                ORDER  BY id DESC
            """)).fetchall()

        resultado = []
        for row in rows:
            (
                id_,
                fecha,
                cuenta,
                total,
                conciliados,
                pendientes,
                tasa,
                periodo,
                mes,
                anio,
                ruta_reporte,
                id_lote,
                estado,
            ) = row[:13]
            resultado.append(
                {
                    "id": id_,
                    "fecha": fecha or "",
                    "cuenta": cuenta or "—",
                    "total": total or 0,
                    "conciliados": conciliados or 0,
                    "pendientes": pendientes or 0,
                    "tasa": tasa or 0.0,
                    "efectividad": f"{(tasa or 0.0):.1f}%",
                    "estado": estado or "COMPLETADO",
                    "periodo": periodo or "",
                    "mes": mes,
                    "anio": anio,
                    "ruta_reporte": ruta_reporte or "",
                    "id_lote": id_lote,
                }
            )

        return {"historial": resultado, "total": len(resultado)}

    except Exception as e:
        return {"historial": [], "total": 0, "error": str(e)}


# ══════════════════════════════════════════════════════════════════
# ENDPOINT 9 — Estadísticas por fase para una cuenta
# Permite a F1/F2/F3/F4/F5 mostrar sus propios datos reales
# ══════════════════════════════════════════════════════════════════
@router.get("/stats-por-fase/", tags=["Datos"])
async def stats_por_fase(cuenta: str = Query(...), id_lote: int = Query(...)):
    """
    Retorna conteo de conciliados por fase para una cuenta y lote específico.
    El id_lote identifica unívocamente una ejecución — garantiza datos del mes correcto.
    """
    try:
        with engine.connect() as con:
            # Totales del lote específico
            row = con.execute(
                _sql("""
                SELECT
                    SUM(CASE WHEN estado_tx='CONCILIADO' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN estado_tx='PENDIENTE'  THEN 1 ELSE 0 END),
                    COUNT(*)
                FROM transaccion
                WHERE cuenta_contable = :cuenta AND id_lote = :lote
            """),
                {"cuenta": cuenta, "lote": id_lote},
            ).fetchone()

            total_conciliados = row[0] or 0
            total_pendientes = row[1] or 0
            total_global = row[2] or 0

            # Conteo por fase del lote — agrupa F6g dentro de F6 para compatibilidad
            filas_fase = con.execute(
                _sql("""
                SELECT
                    CASE WHEN c.fase_origen = 'F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
                    COUNT(t.id_transaccion) AS n
                FROM   transaccion t
                JOIN   conciliacion c ON ABS(t.id_conciliacion) = c.id_conciliacion
                WHERE  t.cuenta_contable = :cuenta AND t.id_lote = :lote
                  AND  t.estado_tx = 'CONCILIADO'
                GROUP BY fase
                ORDER BY fase
            """),
                {"cuenta": cuenta, "lote": id_lote},
            ).fetchall()

        fases_resultado = {}
        for fase_key in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F7b"]:
            n = next((r[1] for r in filas_fase if r[0] == fase_key), 0)
            fases_resultado[fase_key] = {
                "conciliados": n,
                "pct_sobre_conciliados": (
                    round(n / total_conciliados * 100, 1) if total_conciliados else 0.0
                ),
                "pct_sobre_total": round(n / total_global * 100, 1) if total_global else 0.0,
            }

        return {
            "cuenta": cuenta,
            "id_lote": id_lote,
            "total_global": total_global,
            "total_conciliados": total_conciliados,
            "pendientes": total_pendientes,
            "pct_conciliados": (
                round(total_conciliados / total_global * 100, 1) if total_global else 0.0
            ),
            "pct_pendientes": (
                round(total_pendientes / total_global * 100, 1) if total_global else 0.0
            ),
            "fases": fases_resultado,
        }

    except Exception as e:
        return {"cuenta": cuenta, "id_lote": id_lote, "error": str(e), "fases": {}}
