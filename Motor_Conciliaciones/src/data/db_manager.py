import sqlite3
from src.core.models import Transaccion


def _connect(ruta_db: str) -> sqlite3.Connection:
    """
    Abre una conexiÃ³n SQLite con:
    - timeout=30s  â†’ espera hasta 30s si la DB estÃ¡ bloqueada
    - WAL mode     â†’ permite lecturas concurrentes mientras se escribe
    - journal_mode=WAL se activa una sola vez y persiste en el archivo
    """
    con = sqlite3.connect(ruta_db, timeout=30, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=30000")
    return con


class DatabaseManager:

    def __init__(self, ruta_db: str):
        self.ruta_db = ruta_db

    def inicializar_tablas(self):
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        script_sql = """
        CREATE TABLE IF NOT EXISTS LOTE_EJECUCION (
            id_lote INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_inicio DATE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'PENDIENTE'
        );

        CREATE TABLE IF NOT EXISTS TRANSACCION (
            id_transaccion  INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion     TEXT    NOT NULL,
            cuenta_contable TEXT    NOT NULL,
            monto_centavos  INTEGER NOT NULL,
            n_diario        INTEGER NOT NULL DEFAULT 0,
            localidad       TEXT    NOT NULL DEFAULT '',
            periodo         TEXT    NOT NULL DEFAULT '',
            tipo            TEXT    NOT NULL DEFAULT '',
            id_lote         INTEGER NOT NULL,
            estado_tx       TEXT    NOT NULL DEFAULT 'PENDIENTE',
            id_conciliacion INTEGER DEFAULT NULL,
            FOREIGN KEY (id_lote) REFERENCES LOTE_EJECUCION(id_lote)
        );

        CREATE TABLE IF NOT EXISTS CONCILIACION (
            id_conciliacion     INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_conciliacion  DATE NOT NULL,
            estado_conciliacion TEXT NOT NULL DEFAULT 'PENDIENTE',
            fase_origen         TEXT NOT NULL DEFAULT 'F?'
        );
        -- MigraciÃ³n: agregar columna si ya existe la tabla sin ella
        -- (se ignora el error si ya existe)

        CREATE INDEX IF NOT EXISTS idx_tx_cuenta    ON TRANSACCION(cuenta_contable);
        CREATE INDEX IF NOT EXISTS idx_tx_estado    ON TRANSACCION(estado_tx);
        CREATE INDEX IF NOT EXISTS idx_tx_n_diario  ON TRANSACCION(n_diario);
        CREATE INDEX IF NOT EXISTS idx_tx_localidad ON TRANSACCION(localidad);
        CREATE INDEX IF NOT EXISTS idx_tx_periodo   ON TRANSACCION(periodo);
        CREATE INDEX IF NOT EXISTS idx_tx_tipo      ON TRANSACCION(tipo);
        CREATE INDEX IF NOT EXISTS idx_tx_lote      ON TRANSACCION(id_lote);

        CREATE TABLE IF NOT EXISTS HISTORIAL_EJECUCION (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha           TEXT    NOT NULL,
            cuenta          TEXT    NOT NULL,
            total           INTEGER NOT NULL DEFAULT 0,
            conciliados     INTEGER NOT NULL DEFAULT 0,
            pendientes      INTEGER NOT NULL DEFAULT 0,
            tasa            REAL    NOT NULL DEFAULT 0.0,
            periodo         TEXT    DEFAULT '',
            mes             INTEGER DEFAULT NULL,
            anio            INTEGER DEFAULT NULL,
            ruta_reporte    TEXT    DEFAULT '',
            id_lote         INTEGER DEFAULT NULL
        );
        """
        cursor.executescript(script_sql)
        # MigraciÃ³n segura: agregar fase_origen si la DB ya existÃ­a sin ella
        try:
            cursor.execute("ALTER TABLE CONCILIACION ADD COLUMN fase_origen TEXT NOT NULL DEFAULT 'F?'")
            conexion.commit()
        except Exception:
            pass  # columna ya existe
        # Tabla para ejecuciones programadas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS EJECUCION_PROGRAMADA (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha_programada TEXT    NOT NULL,
                hora_programada  TEXT    NOT NULL,
                archivo_path     TEXT    NOT NULL,
                archivo_nombre   TEXT    NOT NULL,
                config_json      TEXT    NOT NULL DEFAULT '{}',
                estado           TEXT    NOT NULL DEFAULT 'PENDIENTE',
                creado_en        TEXT    NOT NULL,
                ejecutado_en     TEXT    DEFAULT NULL
            )
        """)
        conexion.commit()
        conexion.close()

    def registrar_ejecucion(self, cuenta: str, total: int, conciliados: int,
                             pendientes: int, tasa: float, periodo: str,
                             mes, anio, ruta_reporte: str, id_lote: int):
        """Guarda una entrada permanente en el historial de ejecuciones."""
        from datetime import datetime
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO HISTORIAL_EJECUCION
                (fecha, cuenta, total, conciliados, pendientes, tasa, periodo, mes, anio, ruta_reporte, id_lote)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (fecha, cuenta, total, conciliados, pendientes, tasa,
              periodo or "", mes, anio, ruta_reporte or "", id_lote))
        conexion.commit()
        conexion.close()

    def limpiar_transacciones_lote(self, id_lote: int):
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("DELETE FROM TRANSACCION WHERE id_lote = ?", (id_lote,))
        conexion.commit()
        conexion.close()

    def insertar_transacciones(self, transacciones: list[tuple]):
        """
        Tuplas:
          (descripcion, cuenta_contable, monto_centavos, n_diario,
           localidad, periodo, tipo, id_lote)
        """
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.executemany("""
            INSERT INTO TRANSACCION
                (descripcion, cuenta_contable, monto_centavos, n_diario,
                 localidad, periodo, tipo, id_lote)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, transacciones)
        conexion.commit()
        conexion.close()

    def contar_pendientes_lote(self, cuenta_contable: str, id_lote: int) -> int:
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM TRANSACCION
            WHERE cuenta_contable = ? AND id_lote = ? AND estado_tx = 'PENDIENTE'
        """, (cuenta_contable, id_lote))
        resultado = cursor.fetchone()[0]
        conexion.close()
        return resultado

    def obtener_periodos_disponibles(self, cuenta_contable: str, id_lote: int) -> list[str]:
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT DISTINCT periodo FROM TRANSACCION
            WHERE cuenta_contable = ? AND id_lote = ? AND estado_tx = 'PENDIENTE'
            ORDER BY periodo;
        """, (cuenta_contable, id_lote))
        resultados = [fila[0] for fila in cursor.fetchall()]
        conexion.close()
        return resultados

    def obtener_localidades_unicas_por_lote(self, cuenta_contable: str, id_lote: int) -> list[str]:
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT DISTINCT localidad FROM TRANSACCION
            WHERE cuenta_contable = ? AND id_lote = ? AND estado_tx = 'PENDIENTE'
            ORDER BY localidad;
        """, (cuenta_contable, id_lote))
        resultados = [fila[0] for fila in cursor.fetchall()]
        conexion.close()
        return resultados

    def obtener_pendientes_por_localidad(self, cuenta_contable: str,
                                          localidad: str, id_lote: int) -> list[tuple]:
        """
        Tuplas:
          (id_transaccion, descripcion, cuenta_contable, monto_centavos,
           n_diario, localidad, periodo, tipo, id_lote)
        """
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id_transaccion, descripcion, cuenta_contable,
                   monto_centavos, n_diario, localidad, periodo, tipo, id_lote
            FROM   TRANSACCION
            WHERE  cuenta_contable = ? AND localidad = ?
              AND  id_lote = ? AND estado_tx = 'PENDIENTE';
        """, (cuenta_contable, localidad, id_lote))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados

    def obtener_todos_pendientes(self, cuenta_contable: str, id_lote: int) -> list[tuple]:
        """
        Devuelve todas las transacciones PENDIENTES del lote sin filtrar por localidad.
        Mismo formato de tupla que obtener_pendientes_por_localidad â€” compatible con
        filas_a_transacciones() en el router.
        Usado por F6 (Subset Sum global) despuÃ©s de que F1-F5 ya actualizaron estados.
        """
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT id_transaccion, descripcion, cuenta_contable,
                   monto_centavos, n_diario, localidad, periodo, tipo, id_lote
            FROM   TRANSACCION
            WHERE  cuenta_contable = ? AND id_lote = ?
              AND  estado_tx = 'PENDIENTE'
        """, (cuenta_contable, id_lote))
        resultados = cursor.fetchall()
        conexion.close()
        return resultados

    def registrar_conciliacion_masiva(self, grupos_conciliados: list[list[Transaccion]], fase_origen: str = "F?"):
        conexion = _connect(self.ruta_db)
        cursor = conexion.cursor()
        try:
            with conexion:
                for grupo in grupos_conciliados:
                    # Guardar fase_origen para saber quÃ© filtro conciliÃ³ este grupo
                    cursor.execute("""
                        INSERT INTO CONCILIACION (fecha_conciliacion, estado_conciliacion, fase_origen)
                        VALUES (CURRENT_DATE, 'FINALIZADO', ?)
                    """, (fase_origen,))
                    id_conci = cursor.lastrowid
                    ids_txs = [tx.id_transaccion for tx in grupo]
                    placeholders = ', '.join(['?'] * len(ids_txs))
                    cursor.execute(f"""
                        UPDATE TRANSACCION
                        SET estado_tx = 'CONCILIADO', id_conciliacion = ?
                        WHERE id_transaccion IN ({placeholders})
                    """, [id_conci] + ids_txs)
            print(f"ðŸ’¾ DB: {len(grupos_conciliados)} conciliaciones registradas. (Fase: {fase_origen})")
        except Exception as e:
            print(f"âŒ Error DB: {e}")
        finally:
            conexion.close()

    def conciliar_por_monto_puro(self, cuenta_contable: str, id_lote: int) -> int:
        """
        Fase 5 â€” ConciliaciÃ³n solo por monto exacto, sin localidad ni n_diario.
        Estrategia: agrupar por monto, procesar cada monto por separado â†’ sin JOIN explosivo.
        """
        conexion = _connect(self.ruta_db)
        cursor   = conexion.cursor()
        total_conciliados = 0

        try:
            # Paso 1: verificaciÃ³n rÃ¡pida â€” Â¿hay algo que cruzar?
            cursor.execute("""
                SELECT COUNT(DISTINCT monto_centavos) FROM TRANSACCION
                WHERE cuenta_contable = ? AND id_lote = ?
                  AND estado_tx = 'PENDIENTE' AND monto_centavos > 0
            """, (cuenta_contable, id_lote))
            n_pos = cursor.fetchone()[0]
            if n_pos == 0:
                return 0

            # Paso 2: para cada monto, emparejar positivos con negativos uno a uno
            # Usar tabla temporal para el matching masivo â€” mÃ¡s rÃ¡pido que N queries
            cursor.execute("""
                CREATE TEMP TABLE IF NOT EXISTS _pos_ids AS
                SELECT id_transaccion, monto_centavos
                FROM TRANSACCION
                WHERE cuenta_contable = ? AND id_lote = ?
                  AND estado_tx = 'PENDIENTE' AND monto_centavos > 0
            """, (cuenta_contable, id_lote))

            cursor.execute("""
                CREATE TEMP TABLE IF NOT EXISTS _neg_ids AS
                SELECT id_transaccion, monto_centavos
                FROM TRANSACCION
                WHERE cuenta_contable = ? AND id_lote = ?
                  AND estado_tx = 'PENDIENTE' AND monto_centavos < 0
            """, (cuenta_contable, id_lote))

            # Matching: join por monto, row_number para emparejar 1:1
            cursor.execute("""
                SELECT p.id_transaccion, n.id_transaccion
                FROM (
                    SELECT id_transaccion, monto_centavos,
                           ROW_NUMBER() OVER (PARTITION BY monto_centavos ORDER BY id_transaccion) AS rn
                    FROM _pos_ids
                ) p
                JOIN (
                    SELECT id_transaccion, monto_centavos,
                           ROW_NUMBER() OVER (PARTITION BY monto_centavos ORDER BY id_transaccion) AS rn
                    FROM _neg_ids
                ) n ON p.monto_centavos = -n.monto_centavos AND p.rn = n.rn
            """)
            parejas = cursor.fetchall()

            cursor.execute("DROP TABLE IF EXISTS _pos_ids")
            cursor.execute("DROP TABLE IF EXISTS _neg_ids")

            print(f"   ðŸ’¡ F5: {len(parejas):,} parejas Ãºnicas 1:1 por monto")

            # Paso 3: registrar en DB en lotes
            BATCH = 5_000
            with conexion:
                for i in range(0, len(parejas), BATCH):
                    lote = parejas[i:i+BATCH]
                    ids_actualizacion = []
                    for id_pos, id_neg in lote:
                        cursor.execute("""
                            INSERT INTO CONCILIACION (fecha_conciliacion, estado_conciliacion, fase_origen)
                            VALUES (CURRENT_DATE, 'FINALIZADO', 'F5')
                        """)
                        id_conci = cursor.lastrowid
                        ids_actualizacion.append((id_conci, id_pos, id_neg))

                    cursor.executemany("""
                        UPDATE TRANSACCION SET estado_tx='CONCILIADO', id_conciliacion=?
                        WHERE id_transaccion=? AND estado_tx='PENDIENTE'
                    """, [(ic, ip) for ic, ip, _ in ids_actualizacion])
                    cursor.executemany("""
                        UPDATE TRANSACCION SET estado_tx='CONCILIADO', id_conciliacion=?
                        WHERE id_transaccion=? AND estado_tx='PENDIENTE'
                    """, [(ic, in_) for ic, _, in_ in ids_actualizacion])
                    total_conciliados += len(lote) * 2
                    print(f"   ðŸ’¾ F5 lote {i//BATCH+1}: {len(lote)*2:,} regs")

        except Exception as e:
            print(f"âŒ Error F5: {e}")
            import traceback; traceback.print_exc()
        finally:
            conexion.close()

        return total_conciliados
