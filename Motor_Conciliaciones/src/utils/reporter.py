import polars as pl
from datetime import datetime
import os
import xlsxwriter
import sqlite3


class ReconciliationReporter:
    def __init__(self, ruta_salida: str = "reportes/"):
        self.ruta_salida = ruta_salida
        if not os.path.exists(self.ruta_salida):
            os.makedirs(self.ruta_salida)

    def generar_excel_desde_db(self, db, cuenta: str, id_lote: int):
        """
        Lee directamente desde la DB sin límite de filas.
        Escribe el Excel en streaming para no explotar la RAM.
        """
        conexion = sqlite3.connect(db.ruta_db)
        cursor   = conexion.cursor()

        # ── Conteos de resumen ────────────────────────────────────
        cursor.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN tipo='SIF82' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN tipo='TES82' THEN 1 ELSE 0 END)
            FROM   TRANSACCION
            WHERE  cuenta_contable = ? AND id_lote = ? AND estado_tx = 'CONCILIADO'
        """, (cuenta, id_lote))
        r = cursor.fetchone()
        total_conci = r[0] or 0
        sif_conci   = r[1] or 0
        tes_conci   = r[2] or 0

        cursor.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN tipo='SIF82' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN tipo='TES82' THEN 1 ELSE 0 END)
            FROM   TRANSACCION
            WHERE  cuenta_contable = ? AND id_lote = ? AND estado_tx = 'PENDIENTE'
        """, (cuenta, id_lote))
        r = cursor.fetchone()
        total_pend = r[0] or 0
        sif_pend   = r[1] or 0
        tes_pend   = r[2] or 0

        total      = total_conci + total_pend
        tasa       = round(total_conci / total * 100, 2) if total else 0

        # ── Archivo Excel ─────────────────────────────────────────
        timestamp      = datetime.now().strftime("%Y%m%d_%H%M%S")
        nombre_archivo = os.path.join(
            self.ruta_salida, f"resultado_conciliacion_{timestamp}.xlsx"
        )

        workbook = xlsxwriter.Workbook(nombre_archivo, {"constant_memory": True})

        # ── Formatos ──────────────────────────────────────────────
        fmt_header = workbook.add_format({
            "bold": True, "bg_color": "#1e3a5f", "font_color": "white",
            "border": 1, "align": "center", "valign": "vcenter"
        })
        fmt_header_green = workbook.add_format({
            "bold": True, "bg_color": "#1a5c2e", "font_color": "white",
            "border": 1, "align": "center"
        })
        fmt_header_orange = workbook.add_format({
            "bold": True, "bg_color": "#7a3e00", "font_color": "white",
            "border": 1, "align": "center"
        })
        fmt_money_pos = workbook.add_format({"num_format": "#,##0.00", "font_color": "#1a5c2e"})
        fmt_money_neg = workbook.add_format({"num_format": "#,##0.00", "font_color": "#c0392b"})
        fmt_money     = workbook.add_format({"num_format": "#,##0.00"})
        fmt_alt       = workbook.add_format({"bg_color": "#f0f4f8"})
        fmt_label     = workbook.add_format({"bold": True})
        fmt_value     = workbook.add_format({"num_format": "#,##0.##"})

        # ══════════════════════════════════════════════════════════
        # HOJA 1 — RESUMEN
        # ══════════════════════════════════════════════════════════
        ws_res = workbook.add_worksheet("RESUMEN")
        ws_res.set_column("A:A", 35)
        ws_res.set_column("B:B", 20)

        ws_res.write(0, 0, "Concepto", fmt_header)
        ws_res.write(0, 1, "Valor",    fmt_header)

        filas_res = [
            ("Total registros procesados", total),
            ("Conciliados",                total_conci),
            ("Pendientes",                 total_pend),
            ("Tasa de conciliación (%)",   tasa),
            ("─" * 30,                     ""),
            ("SIF82 conciliados",          sif_conci),
            ("TES82 conciliados",          tes_conci),
            ("SIF82 pendientes",           sif_pend),
            ("TES82 pendientes",           tes_pend),
            ("─" * 30,                     ""),
            ("─" * 30,                     ""),
            ("Hoja F1 (Fast-Pass 1:1)",    ""),
            ("Hoja F2 (Subset Sum N:N)",   ""),
            ("Hoja F3 (Tolerancia ±5 cts)",""),
            ("Hoja F4 (Monto+Localidad)",  ""),
            ("Hoja F5 (Monto Puro Global)",""),
            ("Hoja LOGRADO (todos + fase)",total_conci),
            ("Hoja PENDIENTES (registros)",total_pend),
        ]
        for i, (concepto, valor) in enumerate(filas_res, 1):
            ws_res.write(i, 0, concepto, fmt_label)
            ws_res.write(i, 1, valor,    fmt_value if isinstance(valor, (int,float)) else None)

        # ══════════════════════════════════════════════════════════
        # HOJAS 2-7 — Una hoja por fase (F1-F5) + LOGRADO total
        # ══════════════════════════════════════════════════════════
        BATCH = 10_000

        # Colores de header por fase
        fase_config = {
            "F1": {"color": "#1a5c2e", "nombre": "F1 - Fast-Pass (1:1 exacto)",       "fmt": None},
            "F2": {"color": "#1e3a8a", "nombre": "F2 - Subset Sum (N:N suma cero)",   "fmt": None},
            "F3": {"color": "#7c3a00", "nombre": "F3 - Tolerancia ±5 centavos",       "fmt": None},
            "F4": {"color": "#4a1d6e", "nombre": "F4 - Monto+Localidad (sin diario)", "fmt": None},
            "F5": {"color": "#0f4c5c", "nombre": "F5 - Monto Puro Global",            "fmt": None},
        }

        # Crear formatos de header por fase
        for fase, cfg in fase_config.items():
            cfg["fmt"] = workbook.add_format({
                "bold": True, "bg_color": cfg["color"], "font_color": "white",
                "border": 1, "align": "center"
            })

        headers_log = ["Grupo_ID", "ID_Tx", "Tipo", "Período",
                       "Descripción", "Cuenta", "Localidad", "Monto (COP)", "Fase"]

        def _escribir_hoja_fase(ws, fmt_hdr, fase_label, nombre_fase):
            """Escribe registros de una fase específica en streaming."""
            # Descripción en fila 0
            fmt_desc = workbook.add_format({"italic": True, "font_color": "#555555", "font_size": 9})
            ws.merge_range(0, 0, 0, 7, nombre_fase, fmt_desc)

            # Headers en fila 1
            for c, h in enumerate(headers_log[:-1]):  # sin columna Fase (redundante en hoja propia)
                ws.write(1, c, h, fmt_hdr)

            ws.set_column("A:A", 12)
            ws.set_column("B:B", 10)
            ws.set_column("C:C", 8)
            ws.set_column("D:D", 12)
            ws.set_column("E:E", 35)
            ws.set_column("F:F", 14)
            ws.set_column("G:G", 14)
            ws.set_column("H:H", 16)

            offset = 0
            fila = 2  # empieza en fila 2 (fila 0=descripción, 1=headers)
            while True:
                cursor.execute("""
                    SELECT ABS(t.id_conciliacion), t.id_transaccion, t.tipo, t.periodo,
                           t.descripcion, t.cuenta_contable, t.localidad,
                           ROUND(CAST(t.monto_centavos AS REAL) / 100, 2)
                    FROM   TRANSACCION t
                    JOIN   CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
                    WHERE  t.cuenta_contable = ?
                      AND  t.id_lote = ?
                      AND  t.estado_tx = 'CONCILIADO'
                      AND  c.fase_origen = ?
                    ORDER  BY ABS(t.id_conciliacion), t.id_transaccion
                    LIMIT  ? OFFSET ?
                """, (cuenta, id_lote, fase_label, BATCH, offset))
                rows = cursor.fetchall()
                if not rows:
                    break
                for row in rows:
                    grupo_id, id_tx, tipo, periodo, desc, cta, loc, monto = row
                    fmt_bg = fmt_alt if fila % 2 == 0 else None
                    ws.write(fila, 0, grupo_id, fmt_bg)
                    ws.write(fila, 1, id_tx,    fmt_bg)
                    ws.write(fila, 2, tipo,      fmt_bg)
                    ws.write(fila, 3, periodo,   fmt_bg)
                    ws.write(fila, 4, desc,      fmt_bg)
                    ws.write(fila, 5, cta,       fmt_bg)
                    ws.write(fila, 6, loc,       fmt_bg)
                    ws.write(fila, 7, monto,     fmt_money_neg if (monto or 0) < 0 else fmt_money_pos)
                    fila += 1
                offset += BATCH
                if len(rows) < BATCH:
                    break

            if fila > 2:
                ws.freeze_panes(2, 0)
                ws.autofilter(1, 0, fila - 1, 7)
            else:
                # Hoja vacía — poner mensaje
                ws.write(2, 0, f"Sin registros conciliados por {fase_label} en este lote.",
                         workbook.add_format({"italic": True, "font_color": "#aaaaaa"}))
            return fila - 2  # registros escritos

        # Actualizar resumen con conteos por fase antes de escribir las hojas
        conteos_fase = {}
        for fase_key in fase_config:
            cursor.execute("""
                SELECT COUNT(t.id_transaccion)
                FROM   TRANSACCION t
                JOIN   CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
                WHERE  t.cuenta_contable = ? AND t.id_lote = ?
                  AND  t.estado_tx = 'CONCILIADO' AND c.fase_origen = ?
            """, (cuenta, id_lote, fase_key))
            conteos_fase[fase_key] = cursor.fetchone()[0] or 0

        # Agregar conteos de fase al RESUMEN (ws_res ya existe)
        fila_res = len([
            "Total registros procesados", "Conciliados", "Pendientes",
            "Tasa de conciliación (%)", "─", "SIF82 conciliados",
            "TES82 conciliados", "SIF82 pendientes", "TES82 pendientes",
            "─", "Hoja LOGRADO", "Hoja PENDIENTES"
        ]) + 1
        ws_res.write(fila_res, 0, "─" * 30, fmt_label)
        ws_res.write(fila_res, 1, "", None)
        fila_res += 1
        ws_res.write(fila_res, 0, "Desglose por fase", fmt_label)
        ws_res.write(fila_res, 1, "", None)
        fila_res += 1
        for fase_key, cfg in fase_config.items():
            fmt_fase_label = workbook.add_format({"bold": True, "font_color": cfg["color"]})
            ws_res.write(fila_res, 0, f"  {cfg['nombre']}", fmt_fase_label)
            ws_res.write(fila_res, 1, conteos_fase.get(fase_key, 0), fmt_value)
            fila_res += 1

        # Escribir las 5 hojas de fase
        for fase_key, cfg in fase_config.items():
            tab_name = fase_key  # "F1", "F2", etc. — nombre corto de pestaña
            ws_fase = workbook.add_worksheet(tab_name)
            _escribir_hoja_fase(ws_fase, cfg["fmt"], fase_key, cfg["nombre"])

        # Hoja LOGRADO = todos juntos con columna Fase (para referencia completa)
        ws_log = workbook.add_worksheet("LOGRADO")
        ws_log.set_column("A:A", 12)
        ws_log.set_column("B:B", 10)
        ws_log.set_column("C:C", 8)
        ws_log.set_column("D:D", 12)
        ws_log.set_column("E:E", 35)
        ws_log.set_column("F:F", 14)
        ws_log.set_column("G:G", 14)
        ws_log.set_column("H:H", 16)
        ws_log.set_column("I:I", 6)   # Fase

        for c, h in enumerate(headers_log):
            ws_log.write(0, c, h, fmt_header_green)

        offset = 0
        fila   = 1
        while True:
            cursor.execute("""
                SELECT ABS(t.id_conciliacion), t.id_transaccion, t.tipo, t.periodo,
                       t.descripcion, t.cuenta_contable, t.localidad,
                       ROUND(CAST(t.monto_centavos AS REAL) / 100, 2),
                       COALESCE(c.fase_origen, 'F?')
                FROM   TRANSACCION t
                LEFT JOIN CONCILIACION c ON ABS(t.id_conciliacion) = c.id_conciliacion
                WHERE  t.cuenta_contable = ?
                  AND  t.id_lote = ?
                  AND  t.estado_tx = 'CONCILIADO'
                ORDER  BY COALESCE(c.fase_origen,'F?'), ABS(t.id_conciliacion), t.id_transaccion
                LIMIT  ? OFFSET ?
            """, (cuenta, id_lote, BATCH, offset))
            rows = cursor.fetchall()
            if not rows:
                break
            for row in rows:
                grupo_id, id_tx, tipo, periodo, desc, cta, loc, monto, fase_orig = row
                fmt_bg = fmt_alt if fila % 2 == 0 else None
                ws_log.write(fila, 0, grupo_id,   fmt_bg)
                ws_log.write(fila, 1, id_tx,      fmt_bg)
                ws_log.write(fila, 2, tipo,        fmt_bg)
                ws_log.write(fila, 3, periodo,     fmt_bg)
                ws_log.write(fila, 4, desc,        fmt_bg)
                ws_log.write(fila, 5, cta,         fmt_bg)
                ws_log.write(fila, 6, loc,         fmt_bg)
                ws_log.write(fila, 7, monto,       fmt_money_neg if (monto or 0) < 0 else fmt_money_pos)
                ws_log.write(fila, 8, fase_orig,   fmt_bg)
                fila += 1
            offset += BATCH
            if len(rows) < BATCH:
                break

        ws_log.freeze_panes(1, 0)
        ws_log.autofilter(0, 0, fila - 1, len(headers_log) - 1)

        # ══════════════════════════════════════════════════════════
        # HOJA 3 — PENDIENTES (todos los registros, streaming)
        # ══════════════════════════════════════════════════════════
        ws_pend = workbook.add_worksheet("PENDIENTES")
        ws_pend.set_column("A:A", 10)  # ID_Tx
        ws_pend.set_column("B:B", 8)   # Tipo
        ws_pend.set_column("C:C", 12)  # Período
        ws_pend.set_column("D:D", 35)  # Descripción
        ws_pend.set_column("E:E", 14)  # Cuenta
        ws_pend.set_column("F:F", 14)  # Localidad
        ws_pend.set_column("G:G", 16)  # Monto

        headers_pend = ["ID_Tx", "Tipo", "Período", "Descripción",
                        "Cuenta", "Localidad", "Monto (COP)"]
        for c, h in enumerate(headers_pend):
            ws_pend.write(0, c, h, fmt_header_orange)

        offset = 0
        fila   = 1
        while True:
            cursor.execute("""
                SELECT t.id_transaccion, t.tipo, t.periodo,
                       t.descripcion, t.cuenta_contable, t.localidad,
                       ROUND(CAST(t.monto_centavos AS REAL) / 100, 2)
                FROM   TRANSACCION t
                WHERE  t.cuenta_contable = ?
                  AND  t.id_lote = ?
                  AND  t.estado_tx = 'PENDIENTE'
                ORDER  BY t.tipo, t.periodo, t.localidad
                LIMIT  ? OFFSET ?
            """, (cuenta, id_lote, BATCH, offset))
            rows = cursor.fetchall()
            if not rows:
                break

            for row in rows:
                id_tx, tipo, periodo, desc, cta, loc, monto = row
                fmt_bg = fmt_alt if fila % 2 == 0 else None
                ws_pend.write(fila, 0, id_tx,   fmt_bg)
                ws_pend.write(fila, 1, tipo,    fmt_bg)
                ws_pend.write(fila, 2, periodo, fmt_bg)
                ws_pend.write(fila, 3, desc,    fmt_bg)
                ws_pend.write(fila, 4, cta,     fmt_bg)
                ws_pend.write(fila, 5, loc,     fmt_bg)
                if monto is not None and monto < 0:
                    ws_pend.write(fila, 6, monto, fmt_money_neg)
                else:
                    ws_pend.write(fila, 6, monto, fmt_money_pos)
                fila += 1

            offset += BATCH
            if len(rows) < BATCH:
                break

        ws_pend.freeze_panes(1, 0)
        ws_pend.autofilter(0, 0, fila - 1, len(headers_pend) - 1)

        conexion.close()
        workbook.close()

        print(f"📊 Reporte generado: {nombre_archivo} "
              f"({total_conci:,} conciliados | {total_pend:,} pendientes)")
        return nombre_archivo

    def generar_excel_final(self, conciliadas, pendientes):
        """Compatibilidad con llamadas antiguas."""
        print("⚠️  generar_excel_final() — usar generar_excel_desde_db()")
        return None