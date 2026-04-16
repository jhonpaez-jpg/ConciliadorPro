"""
DatabaseManager — capa de acceso a datos.
Funciona con SQLite (local), MySQL y PostgreSQL sin cambiar nada más.
Todos los nombres de tablas en minúsculas — compatible con MySQL en Linux (case-sensitive).
"""

from datetime import datetime, date
from src.core.models import Transaccion
from src.data.db_connection import engine, IS_POSTGRES, IS_MYSQL, get_connection
from sqlalchemy import text


def _serial() -> str:
    if IS_POSTGRES:
        return "BIGSERIAL"
    if IS_MYSQL:
        return "BIGINT"
    return "INTEGER"


def _autoincrement() -> str:
    if IS_POSTGRES:
        return ""
    if IS_MYSQL:
        return "AUTO_INCREMENT"
    return "AUTOINCREMENT"


def _bigint() -> str:
    return "BIGINT" if (IS_POSTGRES or IS_MYSQL) else "INTEGER"


def _text_default(val: str) -> str:
    """
    MySQL no permite DEFAULT en columnas TEXT.
    Usa VARCHAR(255) para columnas cortas con default, TEXT para las demás.
    """
    if IS_MYSQL:
        return f"VARCHAR(255) NOT NULL DEFAULT '{val}'"
    return f"TEXT NOT NULL DEFAULT '{val}'"


def _text_default_null(val: str) -> str:
    if IS_MYSQL:
        return f"VARCHAR(500) DEFAULT '{val}'"
    return f"TEXT DEFAULT '{val}'"


class DatabaseManager:

    def __init__(self, ruta_db: str = "conciliacion.db"):
        self.ruta_db = ruta_db

    def inicializar_tablas(self):
        serial = _serial()
        autoincr = _autoincrement()
        bigint = _bigint()

        # MySQL no permite DEFAULT en TEXT — usar VARCHAR para columnas con default
        t_estado    = _text_default("PENDIENTE")
        t_estado_tx = _text_default("PENDIENTE")
        t_localidad = _text_default("")
        t_periodo   = _text_default("")
        t_tipo      = _text_default("")
        t_fase      = _text_default("F?")
        t_est_conci = _text_default("PENDIENTE")
        t_est_comp  = _text_default_null("COMPLETADO")
        t_per_null  = _text_default_null("")
        t_ruta      = _text_default_null("")

        stmts = [
            f"""CREATE TABLE IF NOT EXISTS lote_ejecucion (
                id_lote      {serial} PRIMARY KEY {autoincr},
                fecha_inicio DATE NOT NULL,
                estado       {t_estado}
            )""",
            f"""CREATE TABLE IF NOT EXISTS transaccion (
                id_transaccion  {serial} PRIMARY KEY {autoincr},
                descripcion     TEXT    NOT NULL,
                cuenta_contable TEXT    NOT NULL,
                monto_centavos  {bigint} NOT NULL,
                n_diario        {bigint} NOT NULL DEFAULT 0,
                localidad       {t_localidad},
                periodo         {t_periodo},
                tipo            {t_tipo},
                id_lote         {bigint} NOT NULL,
                estado_tx       {t_estado_tx},
                id_conciliacion {bigint} DEFAULT NULL
            )""",
            f"""CREATE TABLE IF NOT EXISTS conciliacion (
                id_conciliacion     {serial} PRIMARY KEY {autoincr},
                fecha_conciliacion  DATE NOT NULL,
                estado_conciliacion {t_est_conci},
                fase_origen         {t_fase}
            )""",
            f"""CREATE TABLE IF NOT EXISTS historial_ejecucion (
                id           {serial} PRIMARY KEY {autoincr},
                fecha        TEXT    NOT NULL,
                cuenta       TEXT    NOT NULL,
                total        INTEGER NOT NULL DEFAULT 0,
                conciliados  INTEGER NOT NULL DEFAULT 0,
                pendientes   INTEGER NOT NULL DEFAULT 0,
                tasa         REAL    NOT NULL DEFAULT 0.0,
                periodo      {t_per_null},
                mes          INTEGER DEFAULT NULL,
                anio         INTEGER DEFAULT NULL,
                ruta_reporte {t_ruta},
                id_lote      {bigint} DEFAULT NULL,
                estado       {t_est_comp}
            )""",
            f"""CREATE TABLE IF NOT EXISTS ejecucion_programada (
                id               {serial} PRIMARY KEY {autoincr},
                fecha_programada TEXT    NOT NULL,
                hora_programada  TEXT    NOT NULL,
                archivo_path     TEXT    NOT NULL,
                archivo_nombre   TEXT    NOT NULL,
                config_json      TEXT    NOT NULL,
                estado           {t_estado},
                creado_en        TEXT    NOT NULL,
                ejecutado_en     TEXT    DEFAULT NULL
            )""",
        ]

        # Índices — MySQL no soporta IF NOT EXISTS, se captura el error de duplicado
        indices = [
            "CREATE INDEX idx_tx_cuenta    ON transaccion(cuenta_contable(50))",
            "CREATE INDEX idx_tx_estado    ON transaccion(estado_tx(20))",
            "CREATE INDEX idx_tx_n_diario  ON transaccion(n_diario)",
            "CREATE INDEX idx_tx_localidad ON transaccion(localidad(191))",
            "CREATE INDEX idx_tx_periodo   ON transaccion(periodo(20))",
            "CREATE INDEX idx_tx_tipo      ON transaccion(tipo(10))",
            "CREATE INDEX idx_tx_lote      ON transaccion(id_lote)",
        ] if IS_MYSQL else [
            "CREATE INDEX IF NOT EXISTS idx_tx_cuenta    ON transaccion(cuenta_contable)",
            "CREATE INDEX IF NOT EXISTS idx_tx_estado    ON transaccion(estado_tx)",
            "CREATE INDEX IF NOT EXISTS idx_tx_n_diario  ON transaccion(n_diario)",
            "CREATE INDEX IF NOT EXISTS idx_tx_localidad ON transaccion(localidad)",
            "CREATE INDEX IF NOT EXISTS idx_tx_periodo   ON transaccion(periodo)",
            "CREATE INDEX IF NOT EXISTS idx_tx_tipo      ON transaccion(tipo)",
            "CREATE INDEX IF NOT EXISTS idx_tx_lote      ON transaccion(id_lote)",
        ]

        for stmt in stmts + indices:
            try:
                with engine.begin() as con:
                    con.execute(text(stmt.strip()))
            except Exception as e:
                msg = str(e).lower()
                if "already exists" not in msg and "duplicate" not in msg:
                    print(f"⚠️ inicializar_tablas: {e}")

        # Migraciones seguras
        migrations = [
            "ALTER TABLE conciliacion ADD COLUMN fase_origen TEXT NOT NULL DEFAULT 'F?'",
            "ALTER TABLE historial_ejecucion ADD COLUMN estado TEXT DEFAULT 'COMPLETADO'",
        ]
        if IS_POSTGRES:
            migrations += [
                "ALTER TABLE transaccion ALTER COLUMN monto_centavos TYPE BIGINT",
                "ALTER TABLE transaccion ALTER COLUMN n_diario TYPE BIGINT",
                "ALTER TABLE transaccion ALTER COLUMN id_lote TYPE BIGINT",
                "ALTER TABLE transaccion ALTER COLUMN id_conciliacion TYPE BIGINT",
                "ALTER TABLE historial_ejecucion ALTER COLUMN id_lote TYPE BIGINT",
            ]
        elif IS_MYSQL:
            migrations += [
                "ALTER TABLE transaccion MODIFY COLUMN monto_centavos BIGINT NOT NULL",
                "ALTER TABLE transaccion MODIFY COLUMN n_diario BIGINT NOT NULL DEFAULT 0",
                "ALTER TABLE transaccion MODIFY COLUMN id_lote BIGINT NOT NULL",
                "ALTER TABLE transaccion MODIFY COLUMN id_conciliacion BIGINT DEFAULT NULL",
                "ALTER TABLE historial_ejecucion MODIFY COLUMN id_lote BIGINT DEFAULT NULL",
            ]
        for alter in migrations:
            try:
                with engine.begin() as con:
                    con.execute(text(alter))
            except Exception:
                pass

    def registrar_ejecucion(self, cuenta, total, conciliados, pendientes, tasa,
                             periodo, mes, anio, ruta_reporte, id_lote, estado="COMPLETADO"):
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        with engine.begin() as con:
            con.execute(text("""
                INSERT INTO historial_ejecucion
                    (fecha, cuenta, total, conciliados, pendientes, tasa,
                     periodo, mes, anio, ruta_reporte, id_lote, estado)
                VALUES (:fecha, :cuenta, :total, :conciliados, :pendientes, :tasa,
                        :periodo, :mes, :anio, :ruta_reporte, :id_lote, :estado)
            """), {"fecha": fecha, "cuenta": cuenta, "total": total,
                   "conciliados": conciliados, "pendientes": pendientes, "tasa": tasa,
                   "periodo": periodo or "", "mes": mes, "anio": anio,
                   "ruta_reporte": ruta_reporte or "", "id_lote": id_lote, "estado": estado})

    def limpiar_transacciones_lote(self, id_lote: int):
        with engine.begin() as con:
            con.execute(text("DELETE FROM transaccion WHERE id_lote = :lote"), {"lote": id_lote})

    def insertar_transacciones(self, transacciones: list[tuple]):
        if not transacciones:
            return
        rows = [{"desc": t[0], "cta": t[1], "monto": t[2], "ndiario": t[3],
                 "loc": t[4], "per": t[5], "tipo": t[6], "lote": t[7]}
                for t in transacciones]
        with engine.begin() as con:
            con.execute(text("""
                INSERT INTO transaccion
                    (descripcion, cuenta_contable, monto_centavos, n_diario,
                     localidad, periodo, tipo, id_lote)
                VALUES (:desc, :cta, :monto, :ndiario, :loc, :per, :tipo, :lote)
            """), rows)

    def contar_pendientes_lote(self, cuenta_contable: str, id_lote: int) -> int:
        with get_connection() as con:
            row = con.execute(text("""
                SELECT COUNT(*) FROM transaccion
                WHERE cuenta_contable = :cta AND id_lote = :lote AND estado_tx = 'PENDIENTE'
            """), {"cta": cuenta_contable, "lote": id_lote}).fetchone()
        return row[0] if row else 0

    def obtener_periodos_disponibles(self, cuenta_contable: str, id_lote: int) -> list[str]:
        with get_connection() as con:
            rows = con.execute(text("""
                SELECT DISTINCT periodo FROM transaccion
                WHERE cuenta_contable = :cta AND id_lote = :lote AND estado_tx = 'PENDIENTE'
                ORDER BY periodo
            """), {"cta": cuenta_contable, "lote": id_lote}).fetchall()
        return [r[0] for r in rows]

    def obtener_localidades_unicas_por_lote(self, cuenta_contable: str, id_lote: int) -> list[str]:
        with get_connection() as con:
            rows = con.execute(text("""
                SELECT DISTINCT localidad FROM transaccion
                WHERE cuenta_contable = :cta AND id_lote = :lote AND estado_tx = 'PENDIENTE'
                ORDER BY localidad
            """), {"cta": cuenta_contable, "lote": id_lote}).fetchall()
        return [r[0] for r in rows]

    def obtener_pendientes_por_localidad(self, cuenta_contable: str,
                                          localidad: str, id_lote: int) -> list[tuple]:
        with get_connection() as con:
            rows = con.execute(text("""
                SELECT id_transaccion, descripcion, cuenta_contable,
                       monto_centavos, n_diario, localidad, periodo, tipo, id_lote
                FROM   transaccion
                WHERE  cuenta_contable = :cta AND localidad = :loc
                  AND  id_lote = :lote AND estado_tx = 'PENDIENTE'
            """), {"cta": cuenta_contable, "loc": localidad, "lote": id_lote}).fetchall()
        return [tuple(r) for r in rows]

    def obtener_todos_pendientes(self, cuenta_contable: str, id_lote: int) -> list[tuple]:
        with get_connection() as con:
            rows = con.execute(text("""
                SELECT id_transaccion, descripcion, cuenta_contable,
                       monto_centavos, n_diario, localidad, periodo, tipo, id_lote
                FROM   transaccion
                WHERE  cuenta_contable = :cta AND id_lote = :lote AND estado_tx = 'PENDIENTE'
            """), {"cta": cuenta_contable, "lote": id_lote}).fetchall()
        return [tuple(r) for r in rows]

    def registrar_conciliacion_masiva(self, grupos_conciliados: list[list[Transaccion]],
                                       fase_origen: str = "F?"):
        """
        Registra grupos en batch minimizando round-trips.
        - INSERTs de conciliacion: uno por grupo (necesitamos el ID generado)
        - UPDATEs de transaccion: agrupados en un solo UPDATE con CASE WHEN
        """
        if not grupos_conciliados:
            return
        hoy = date.today().isoformat()
        try:
            with engine.begin() as con:
                # Recopilar todos los pares (id_conci, ids_txs)
                pares = []
                for grupo in grupos_conciliados:
                    result = con.execute(text("""
                        INSERT INTO conciliacion (fecha_conciliacion, estado_conciliacion, fase_origen)
                        VALUES (:fecha, 'FINALIZADO', :fase)
                    """), {"fecha": hoy, "fase": fase_origen})
                    id_conci = result.inserted_primary_key[0] if IS_POSTGRES else result.lastrowid
                    pares.append((id_conci, [tx.id_transaccion for tx in grupo]))

                # UPDATE masivo: un solo statement con CASE WHEN por cada grupo
                # Agrupa todos los ids en un solo UPDATE para reducir round-trips
                BATCH_UPDATE = 200  # grupos por UPDATE
                for i in range(0, len(pares), BATCH_UPDATE):
                    lote = pares[i:i + BATCH_UPDATE]

                    # Construir: UPDATE transaccion SET id_conciliacion = CASE
                    #   WHEN id_transaccion IN (...) THEN id1
                    #   WHEN id_transaccion IN (...) THEN id2
                    # END WHERE id_transaccion IN (todos los ids)
                    case_parts = []
                    all_ids = []
                    params: dict = {}

                    for j, (id_conci, ids_txs) in enumerate(lote):
                        keys = [f"t{j}_{k}" for k in range(len(ids_txs))]
                        in_clause = ", ".join([f":{k}" for k in keys])
                        case_parts.append(
                            f"WHEN id_transaccion IN ({in_clause}) THEN :c{j}"
                        )
                        params[f"c{j}"] = id_conci
                        for k, tx_id in zip(keys, ids_txs):
                            params[k] = tx_id
                        all_ids.extend(keys)

                    all_in = ", ".join([f":{k}" for k in all_ids])
                    case_sql = " ".join(case_parts)

                    con.execute(text(f"""
                        UPDATE transaccion
                        SET estado_tx = 'CONCILIADO',
                            id_conciliacion = CASE {case_sql} END
                        WHERE id_transaccion IN ({all_in})
                          AND estado_tx = 'PENDIENTE'
                    """), params)

            print(f"💾 DB: {len(grupos_conciliados)} conciliaciones. (Fase: {fase_origen})")
        except Exception as e:
            print(f"❌ Error DB: {e}")
            import traceback; traceback.print_exc()

    def conciliar_por_monto_puro(self, cuenta_contable: str, id_lote: int) -> int:
        total_conciliados = 0
        params = {"cta": cuenta_contable, "lote": id_lote}
        try:
            with get_connection() as con:
                n_pos = con.execute(text("""
                    SELECT COUNT(DISTINCT monto_centavos) FROM transaccion
                    WHERE cuenta_contable = :cta AND id_lote = :lote
                      AND estado_tx = 'PENDIENTE' AND monto_centavos > 0
                """), params).scalar()
                if not n_pos:
                    return 0
                parejas = con.execute(text("""
                    SELECT p.id_transaccion, n.id_transaccion
                    FROM (
                        SELECT id_transaccion, monto_centavos,
                               ROW_NUMBER() OVER (PARTITION BY monto_centavos ORDER BY id_transaccion) AS rn
                        FROM transaccion
                        WHERE cuenta_contable = :cta AND id_lote = :lote
                          AND estado_tx = 'PENDIENTE' AND monto_centavos > 0
                    ) p
                    JOIN (
                        SELECT id_transaccion, monto_centavos,
                               ROW_NUMBER() OVER (PARTITION BY monto_centavos ORDER BY id_transaccion) AS rn
                        FROM transaccion
                        WHERE cuenta_contable = :cta AND id_lote = :lote
                          AND estado_tx = 'PENDIENTE' AND monto_centavos < 0
                    ) n ON p.monto_centavos = -n.monto_centavos AND p.rn = n.rn
                """), params).fetchall()

            print(f"   💡 F5: {len(parejas):,} parejas 1:1 por monto")
            hoy = date.today().isoformat()
            BATCH = 5_000
            for i in range(0, len(parejas), BATCH):
                lote = parejas[i:i + BATCH]
                with engine.begin() as con:
                    ids_act = []
                    for id_pos, id_neg in lote:
                        result = con.execute(text("""
                            INSERT INTO conciliacion (fecha_conciliacion, estado_conciliacion, fase_origen)
                            VALUES (:fecha, 'FINALIZADO', 'F5')
                        """), {"fecha": hoy})
                        id_conci = result.inserted_primary_key[0] if IS_POSTGRES else result.lastrowid
                        ids_act.append((id_conci, id_pos, id_neg))
                    for id_conci, id_pos, id_neg in ids_act:
                        con.execute(text("""
                            UPDATE transaccion SET estado_tx='CONCILIADO', id_conciliacion=:ic
                            WHERE id_transaccion=:it AND estado_tx='PENDIENTE'
                        """), {"ic": id_conci, "it": id_pos})
                        con.execute(text("""
                            UPDATE transaccion SET estado_tx='CONCILIADO', id_conciliacion=:ic
                            WHERE id_transaccion=:it AND estado_tx='PENDIENTE'
                        """), {"ic": id_conci, "it": id_neg})
                total_conciliados += len(lote) * 2
                print(f"   💾 F5 lote {i // BATCH + 1}: {len(lote) * 2:,} regs")
        except Exception as e:
            print(f"❌ Error F5: {e}")
            import traceback; traceback.print_exc()
        return total_conciliados
