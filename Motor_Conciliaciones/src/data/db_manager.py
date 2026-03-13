import sqlite3
from src.core.models import Transaccion


class DatabaseManager:

    def __init__(self, ruta_db: str):
        self.ruta_db = ruta_db

    def inicializar_tablas(self):
        conexion = sqlite3.connect(self.ruta_db)
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
        -- Migración: agregar columna si ya existe la tabla sin ella
        -- (se ignora el error si ya existe)

        CREATE INDEX IF NOT EXISTS idx_tx_cuenta    ON TRANSACCION(cuenta_contable);
        CREATE INDEX IF NOT EXISTS idx_tx_estado    ON TRANSACCION(estado_tx);
        CREATE INDEX IF NOT EXISTS idx_tx_n_diario  ON TRANSACCION(n_diario);
        CREATE INDEX IF NOT EXISTS idx_tx_localidad ON TRANSACCION(localidad);
        CREATE INDEX IF NOT EXISTS idx_tx_periodo   ON TRANSACCION(periodo);
        CREATE INDEX IF NOT EXISTS idx_tx_tipo      ON TRANSACCION(tipo);
        CREATE INDEX IF NOT EXISTS idx_tx_lote      ON TRANSACCION(id_lote);
        """
        cursor.executescript(script_sql)
        # Migración segura: agregar fase_origen si la DB ya existía sin ella
        try:
            cursor.execute("ALTER TABLE CONCILIACION ADD COLUMN fase_origen TEXT NOT NULL DEFAULT 'F?'")
            conexion.commit()
        except Exception:
            pass  # columna ya existe
        conexion.commit()
        conexion.close()

    def limpiar_transacciones_lote(self, id_lote: int):
        conexion = sqlite3.connect(self.ruta_db)
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
        conexion = sqlite3.connect(self.ruta_db)
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
        conexion = sqlite3.connect(self.ruta_db)
        cursor = conexion.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM TRANSACCION
            WHERE cuenta_contable = ? AND id_lote = ? AND estado_tx = 'PENDIENTE'
        """, (cuenta_contable, id_lote))
        resultado = cursor.fetchone()[0]
        conexion.close()
        return resultado

    def obtener_periodos_disponibles(self, cuenta_contable: str, id_lote: int) -> list[str]:
        conexion = sqlite3.connect(self.ruta_db)
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
        conexion = sqlite3.connect(self.ruta_db)
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
        conexion = sqlite3.connect(self.ruta_db)
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

    def registrar_conciliacion_masiva(self, grupos_conciliados: list[list[Transaccion]], fase_origen: str = "F?"):
        conexion = sqlite3.connect(self.ruta_db)
        cursor = conexion.cursor()
        try:
            with conexion:
                for grupo in grupos_conciliados:
                    # Guardar fase_origen para saber qué filtro concilió este grupo
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
            print(f"💾 DB: {len(grupos_conciliados)} conciliaciones registradas. (Fase: {fase_origen})")
        except Exception as e:
            print(f"❌ Error DB: {e}")
        finally:
            conexion.close()

    def conciliar_por_monto_puro(self, cuenta_contable: str, id_lote: int) -> int:
        """
        Fase 5 — Conciliación solo por monto exacto, sin localidad ni n_diario.
        Estrategia: agrupar por monto, procesar cada monto por separado → sin JOIN explosivo.
        """
        conexion = sqlite3.connect(self.ruta_db)
        cursor   = conexion.cursor()
        total_conciliados = 0

        try:
            # Paso 1: verificación rápida — ¿hay algo que cruzar?
            cursor.execute("""
                SELECT COUNT(DISTINCT monto_centavos) FROM TRANSACCION
                WHERE cuenta_contable = ? AND id_lote = ?
                  AND estado_tx = 'PENDIENTE' AND monto_centavos > 0
            """, (cuenta_contable, id_lote))
            n_pos = cursor.fetchone()[0]
            if n_pos == 0:
                return 0

            # Paso 2: para cada monto, emparejar positivos con negativos uno a uno
            # Usar tabla temporal para el matching masivo — más rápido que N queries
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

            print(f"   💡 F5: {len(parejas):,} parejas únicas 1:1 por monto")

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
                    print(f"   💾 F5 lote {i//BATCH+1}: {len(lote)*2:,} regs")

        except Exception as e:
            print(f"❌ Error F5: {e}")
            import traceback; traceback.print_exc()
        finally:
            conexion.close()

        return total_conciliados