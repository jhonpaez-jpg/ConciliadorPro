from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import os, io, sqlite3 as sq3, xlsxwriter
from datetime import datetime as dt

# Importar reportlab al nivel del módulo para que todos los helpers lo vean
from reportlab.lib import colors as rl_colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.units import cm
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable

report_router = APIRouter()
DB_PATH = "conciliacion.db"


# ── Helpers PDF ───────────────────────────────────────────────────────────────
def _pdf_base_styles():
    colors = rl_colors
    C = {
        "azul": colors.HexColor("#1e3a5f"),
        "azul2": colors.HexColor("#2563eb"),
        "azul_c": colors.HexColor("#dbeafe"),
        "verde": colors.HexColor("#16a34a"),
        "verde_c": colors.HexColor("#dcfce7"),
        "rojo": colors.HexColor("#dc2626"),
        "rojo_c": colors.HexColor("#fee2e2"),
        "naranja": colors.HexColor("#ea580c"),
        "nar_c": colors.HexColor("#ffedd5"),
        "gris_c": colors.HexColor("#f8fafc"),
        "borde": colors.HexColor("#e2e8f0"),
        "blanco": colors.white,
        "negro": colors.HexColor("#0f172a"),
        "muted": colors.HexColor("#64748b"),
    }
    S = {
        "titulo": ParagraphStyle(
            "t", fontName="Helvetica-Bold", fontSize=20, textColor=C["blanco"], alignment=TA_CENTER
        ),
        "sub": ParagraphStyle(
            "s",
            fontName="Helvetica",
            fontSize=10,
            textColor=colors.HexColor("#93c5fd"),
            alignment=TA_CENTER,
        ),
        "seccion": ParagraphStyle(
            "sc",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=C["azul"],
            spaceBefore=12,
            spaceAfter=5,
        ),
        "normal": ParagraphStyle(
            "n", fontName="Helvetica", fontSize=8, textColor=C["negro"], leading=11
        ),
        "small": ParagraphStyle(
            "sm", fontName="Helvetica", fontSize=7, textColor=C["muted"], leading=10
        ),
        "pie": ParagraphStyle(
            "p", fontName="Helvetica", fontSize=7, textColor=C["muted"], alignment=TA_CENTER
        ),
        "bold": ParagraphStyle("b", fontName="Helvetica-Bold", fontSize=8, textColor=C["negro"]),
        "right": ParagraphStyle(
            "r", fontName="Helvetica", fontSize=8, textColor=C["negro"], alignment=TA_RIGHT
        ),
        "center": ParagraphStyle(
            "c", fontName="Helvetica", fontSize=8, textColor=C["negro"], alignment=TA_CENTER
        ),
        "verde_v": ParagraphStyle(
            "vv", fontName="Helvetica-Bold", fontSize=8, textColor=C["verde"]
        ),
        "rojo_v": ParagraphStyle("rv", fontName="Helvetica-Bold", fontSize=8, textColor=C["rojo"]),
        "azul_v": ParagraphStyle("av", fontName="Helvetica-Bold", fontSize=8, textColor=C["azul2"]),
    }
    return C, S


def _cabecera_pdf(elems, page_w, titulo, subtitulo, C, S):
    colors = rl_colors
    cab = Table([[Paragraph(titulo, S["titulo"])]], colWidths=[page_w])
    cab.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), C["azul"]),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 16),
            ]
        )
    )
    elems.append(cab)
    sub = Table([[Paragraph(subtitulo, S["sub"])]], colWidths=[page_w])
    sub.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1e40af")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    elems.append(sub)
    elems.append(Spacer(1, 14))


def _tabla_std(rows, col_widths, hdr_color, alt_color, C):
    colors = rl_colors
    t = Table(rows, colWidths=col_widths)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), hdr_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), C["blanco"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C["blanco"], alt_color]),
                ("GRID", (0, 0), (-1, -1), 0.3, C["borde"]),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return t


def _pie_pdf(elems, page_w, filename, C, S):

    elems.append(Spacer(1, 16))
    elems.append(HRFlowable(width=page_w, thickness=0.5, color=C["borde"]))
    elems.append(Spacer(1, 4))
    elems.append(
        Paragraph(
            f"Conciliador Pro  ·  {dt.now().strftime('%d/%m/%Y %H:%M')}  ·  {filename}", S["pie"]
        )
    )


def _get_lote_info(cur, id_lote, cuenta):
    cur.execute(
        """
        SELECT COUNT(*),
               SUM(CASE WHEN estado_tx='CONCILIADO' THEN 1 ELSE 0 END),
               SUM(CASE WHEN estado_tx='PENDIENTE'  THEN 1 ELSE 0 END),
               MIN(periodo)
        FROM transaccion WHERE id_lote=? AND cuenta_contable=?
    """,
        (id_lote, cuenta),
    )
    r = cur.fetchone()
    total = r[0] or 0
    conci = r[1] or 0
    pend = r[2] or 0
    per = r[3] or ""
    tasa = round(conci / total * 100, 2) if total else 0
    return total, conci, pend, tasa, per


# ══════════════════════════════════════════════════════════════════
# REPORTE 1 — Conciliación Completa (Excel)
# LOGRADO por fase (F1-F7b), grupos, IDs, combinaciones encontradas
# ══════════════════════════════════════════════════════════════════
@report_router.get("/reporte-conciliacion-completa/", tags=["Reportes Especializados"])
async def reporte_conciliacion_completa(id_lote: int = Query(...), cuenta: str = Query(...)):

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})

    fmt_hdr = wb.add_format(
        {"bold": True, "bg_color": "#1e3a5f", "font_color": "white", "border": 1, "align": "center"}
    )
    fmt_alt = wb.add_format({"bg_color": "#f0f4f8"})
    fmt_money = wb.add_format({"num_format": "#,##0.00"})
    fmt_pos = wb.add_format({"num_format": "#,##0.00", "font_color": "#16a34a"})
    fmt_neg = wb.add_format({"num_format": "#,##0.00", "font_color": "#dc2626"})
    fmt_bold = wb.add_format({"bold": True})
    fmt_pct = wb.add_format({"num_format": "0.0%"})

    FASE_DESC = {
        "F1": "Fast-Pass — 1:1 exacto (n_diario+localidad+monto)",
        "F2": "Subset Sum — N:N suma cero (mismo n_diario y localidad)",
        "F3": "Tolerancia — diferencia ≤ 5 centavos",
        "F4": "Localidad — monto+localidad sin n_diario",
        "F5": "Monto Puro — solo monto (último recurso 1:1)",
        "F6": "Subset Sum Global — N positivos → 1 negativo",
        "F7": "Final Cleaning — 1 positivo → N negativos",
        "F7b": "Final Cleaning B — positivos restantes → N negativos",
    }

    # ── Hoja RESUMEN ──────────────────────────────────────────────
    ws = wb.add_worksheet("RESUMEN")
    ws.set_column("A:A", 38)
    ws.set_column("B:B", 18)
    ws.write(0, 0, "Concepto", fmt_hdr)
    ws.write(0, 1, "Valor", fmt_hdr)
    filas = [
        ("Cuenta contable", cuenta),
        ("Período", periodo),
        ("Total registros", total),
        ("Conciliados", conci),
        ("Pendientes", pend),
        ("Tasa de conciliación (%)", tasa),
        ("Fecha generación", dt.now().strftime("%d/%m/%Y %H:%M")),
    ]
    for i, (k, v) in enumerate(filas, 1):
        ws.write(i, 0, k, fmt_bold)
        ws.write(i, 1, v)

    # Desglose por fase en RESUMEN
    ws.write(len(filas) + 2, 0, "Fase", fmt_hdr)
    ws.write(len(filas) + 2, 1, "Conciliados", fmt_hdr)
    cur.execute(
        """
        SELECT CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END,
               COUNT(t.id_transaccion)
        FROM transaccion t JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
        GROUP BY 1 ORDER BY 1
    """,
        (id_lote, cuenta),
    )
    for i, (fase, n) in enumerate(cur.fetchall(), len(filas) + 3):
        ws.write(i, 0, fase)
        ws.write(i, 1, n)

    # ── Una hoja por fase ─────────────────────────────────────────
    for fase_key in ["F1", "F2", "F3", "F4", "F5", "F6", "F7", "F7b"]:
        cur.execute(
            """
            SELECT ABS(t.id_conciliacion), t.id_transaccion, t.tipo, t.periodo,
                   t.descripcion, t.localidad, ROUND(CAST(t.monto_centavos AS REAL)/100,2)
            FROM transaccion t JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
            WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
              AND (c.fase_origen=? OR (? = 'F6' AND c.fase_origen='F6g'))
            ORDER BY ABS(t.id_conciliacion), t.id_transaccion
        """,
            (id_lote, cuenta, fase_key, fase_key),
        )
        rows = cur.fetchall()
        ws_f = wb.add_worksheet(fase_key)
        desc = FASE_DESC.get(fase_key, fase_key)
        ws_f.merge_range(
            0,
            0,
            0,
            6,
            desc,
            wb.add_format({"italic": True, "font_color": "#555555", "font_size": 9}),
        )
        hdrs = ["Grupo_ID", "ID_Tx", "Tipo", "Período", "Descripción", "Localidad", "Monto (COP)"]
        for c_, h in enumerate(hdrs):
            ws_f.write(1, c_, h, fmt_hdr)
        ws_f.set_column("E:E", 35)
        ws_f.set_column("G:G", 14)
        for r_, (gid, tid, tipo, per, desc_, loc, monto) in enumerate(rows, 2):
            fmt_bg = fmt_alt if r_ % 2 == 0 else None
            ws_f.write(r_, 0, gid, fmt_bg)
            ws_f.write(r_, 1, tid, fmt_bg)
            ws_f.write(r_, 2, tipo, fmt_bg)
            ws_f.write(r_, 3, per, fmt_bg)
            ws_f.write(r_, 4, desc_, fmt_bg)
            ws_f.write(r_, 5, loc, fmt_bg)
            ws_f.write(r_, 6, monto, fmt_neg if (monto or 0) < 0 else fmt_pos)
        if rows:
            ws_f.autofilter(1, 0, len(rows) + 1, 6)

    # ── Hoja LOGRADO (todos + fase) ───────────────────────────────
    ws_log = wb.add_worksheet("LOGRADO")
    hdrs_log = [
        "Grupo_ID",
        "ID_Tx",
        "Tipo",
        "Período",
        "Descripción",
        "Localidad",
        "Monto (COP)",
        "Fase",
    ]
    for c_, h in enumerate(hdrs_log):
        ws_log.write(0, c_, h, fmt_hdr)
    ws_log.set_column("E:E", 35)
    ws_log.set_column("H:H", 6)
    cur.execute(
        """
        SELECT ABS(t.id_conciliacion), t.id_transaccion, t.tipo, t.periodo,
               t.descripcion, t.localidad, ROUND(CAST(t.monto_centavos AS REAL)/100,2),
               COALESCE(c.fase_origen,'?')
        FROM transaccion t LEFT JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
        ORDER BY COALESCE(c.fase_origen,'ZZ'), ABS(t.id_conciliacion)
    """,
        (id_lote, cuenta),
    )
    for r_, row in enumerate(cur.fetchall(), 1):
        fmt_bg = fmt_alt if r_ % 2 == 0 else None
        for c_, v in enumerate(row):
            ws_log.write(r_, c_, v, fmt_bg)
    ws_log.autofilter(0, 0, r_, 7)

    # ── Hoja PENDIENTES ───────────────────────────────────────────
    ws_p = wb.add_worksheet("PENDIENTES")
    hdrs_p = ["ID_Tx", "Tipo", "Período", "Descripción", "Localidad", "Monto (COP)"]
    for c_, h in enumerate(hdrs_p):
        ws_p.write(0, c_, h, fmt_hdr)
    ws_p.set_column("D:D", 35)
    cur.execute(
        """
        SELECT id_transaccion, tipo, periodo, descripcion, localidad,
               ROUND(CAST(monto_centavos AS REAL)/100,2)
        FROM transaccion WHERE id_lote=? AND cuenta_contable=? AND estado_tx='PENDIENTE'
        ORDER BY tipo, periodo
    """,
        (id_lote, cuenta),
    )
    for r_, row in enumerate(cur.fetchall(), 1):
        fmt_bg = fmt_alt if r_ % 2 == 0 else None
        for c_, v in enumerate(row):
            ws_p.write(r_, c_, v, fmt_bg)

    con.close()
    wb.close()
    buf.seek(0)
    fname = f"conciliacion_completa_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ══════════════════════════════════════════════════════════════════
# REPORTE 2 — Métricas por Fase (Excel)
# Grupos, transacciones, cobertura de negativos por fase
# ══════════════════════════════════════════════════════════════════
@report_router.get("/reporte-metricas-fases/", tags=["Reportes Especializados"])
async def reporte_metricas_fases(id_lote: int = Query(...), cuenta: str = Query(...)):

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fmt_hdr = wb.add_format(
        {"bold": True, "bg_color": "#1e3a5f", "font_color": "white", "border": 1, "align": "center"}
    )
    fmt_alt = wb.add_format({"bg_color": "#f0f4f8"})
    fmt_pct = wb.add_format({"num_format": "0.0%"})
    fmt_bold = wb.add_format({"bold": True})

    # ── Hoja RESUMEN MÉTRICAS ─────────────────────────────────────
    ws = wb.add_worksheet("RESUMEN_METRICAS")
    ws.set_column("A:A", 12)
    ws.set_column("B:B", 42)
    ws.set_column("C:H", 14)
    hdrs = [
        "Fase",
        "Descripción",
        "Grupos",
        "Transacciones",
        "% del Total",
        "% Conciliados",
        "Neg. cubiertos",
        "Pos. usados",
    ]
    for c_, h in enumerate(hdrs):
        ws.write(0, c_, h, fmt_hdr)

    FASE_DESC = {
        "F1": "Fast-Pass — 1:1 exacto",
        "F2": "Subset Sum — N:N suma cero",
        "F3": "Tolerancia ±5 centavos",
        "F4": "Localidad — monto+localidad",
        "F5": "Monto Puro Global",
        "F6": "Subset Sum Global (N pos → 1 neg)",
        "F7": "Final Cleaning (1 pos → N neg)",
        "F7b": "Final Cleaning B (pos restantes)",
    }

    cur.execute(
        """
        SELECT CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
               COUNT(DISTINCT ABS(t.id_conciliacion)) AS grupos,
               COUNT(t.id_transaccion) AS txs,
               SUM(CASE WHEN t.monto_centavos < 0 THEN 1 ELSE 0 END) AS neg,
               SUM(CASE WHEN t.monto_centavos > 0 THEN 1 ELSE 0 END) AS pos
        FROM transaccion t JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
        GROUP BY fase ORDER BY fase
    """,
        (id_lote, cuenta),
    )
    for r_, row in enumerate(cur.fetchall(), 1):
        fase, grupos, txs, neg, pos = row
        pct_total = round(txs / total * 100, 1) if total else 0
        pct_conci = round(txs / conci * 100, 1) if conci else 0
        fmt_bg = fmt_alt if r_ % 2 == 0 else None
        ws.write(r_, 0, fase, fmt_bg)
        ws.write(r_, 1, FASE_DESC.get(fase, fase), fmt_bg)
        ws.write(r_, 2, grupos, fmt_bg)
        ws.write(r_, 3, txs, fmt_bg)
        ws.write(r_, 4, pct_total, fmt_bg)
        ws.write(r_, 5, pct_conci, fmt_bg)
        ws.write(r_, 6, neg, fmt_bg)
        ws.write(r_, 7, pos, fmt_bg)

    # ── Hoja GRUPOS por fase ──────────────────────────────────────
    ws2 = wb.add_worksheet("GRUPOS_POR_FASE")
    ws2.set_column("A:A", 8)
    ws2.set_column("B:B", 12)
    ws2.set_column("C:C", 14)
    hdrs2 = [
        "Fase",
        "Grupo_ID",
        "# Transacciones",
        "Monto Neto (COP)",
        "Suma Positivos",
        "Suma Negativos",
    ]
    for c_, h in enumerate(hdrs2):
        ws2.write(0, c_, h, fmt_hdr)
    ws2.set_column("D:F", 16)
    cur.execute(
        """
        SELECT CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
               ABS(t.id_conciliacion) AS gid,
               COUNT(t.id_transaccion),
               ROUND(SUM(CAST(t.monto_centavos AS REAL)/100),2),
               ROUND(SUM(CASE WHEN t.monto_centavos>0 THEN CAST(t.monto_centavos AS REAL)/100 ELSE 0 END),2),
               ROUND(SUM(CASE WHEN t.monto_centavos<0 THEN CAST(t.monto_centavos AS REAL)/100 ELSE 0 END),2)
        FROM transaccion t JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
        GROUP BY fase, gid ORDER BY fase, gid
    """,
        (id_lote, cuenta),
    )
    for r_, row in enumerate(cur.fetchall(), 1):
        fmt_bg = fmt_alt if r_ % 2 == 0 else None
        for c_, v in enumerate(row):
            ws2.write(r_, c_, v, fmt_bg)
    if r_ > 0:
        ws2.autofilter(0, 0, r_, 5)

    con.close()
    wb.close()
    buf.seek(0)
    fname = f"metricas_fases_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ══════════════════════════════════════════════════════════════════
# REPORTE 3 — Pendientes y Anomalías (Excel)
# Negativos sin cubrir, con/sin contraparte, irresolubles
# ══════════════════════════════════════════════════════════════════
@report_router.get("/reporte-pendientes/", tags=["Reportes Especializados"])
async def reporte_pendientes(id_lote: int = Query(...), cuenta: str = Query(...)):

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    fmt_hdr = wb.add_format(
        {"bold": True, "bg_color": "#7c2d12", "font_color": "white", "border": 1, "align": "center"}
    )
    fmt_alt = wb.add_format({"bg_color": "#fff7ed"})
    fmt_neg = wb.add_format({"num_format": "#,##0.00", "font_color": "#dc2626"})
    fmt_pos = wb.add_format({"num_format": "#,##0.00", "font_color": "#16a34a"})
    fmt_bold = wb.add_format({"bold": True})

    # ── Hoja RESUMEN PENDIENTES ───────────────────────────────────
    ws = wb.add_worksheet("RESUMEN_PENDIENTES")
    ws.set_column("A:A", 35)
    ws.set_column("B:B", 18)
    ws.write(0, 0, "Concepto", fmt_hdr)
    ws.write(0, 1, "Valor", fmt_hdr)
    cur.execute(
        """
        SELECT
            COUNT(*),
            SUM(CASE WHEN monto_centavos<0 THEN 1 ELSE 0 END),
            SUM(CASE WHEN monto_centavos>0 THEN 1 ELSE 0 END),
            ROUND(SUM(CASE WHEN monto_centavos<0 THEN ABS(CAST(monto_centavos AS REAL)/100) ELSE 0 END),2),
            ROUND(SUM(CASE WHEN monto_centavos>0 THEN CAST(monto_centavos AS REAL)/100 ELSE 0 END),2)
        FROM transaccion WHERE id_lote=? AND cuenta_contable=? AND estado_tx='PENDIENTE'
    """,
        (id_lote, cuenta),
    )
    r = cur.fetchone()
    tot_p, neg_p, pos_p, monto_neg, monto_pos = r
    filas = [
        ("Total pendientes", tot_p or 0),
        ("Negativos pendientes", neg_p or 0),
        ("Positivos pendientes", pos_p or 0),
        ("Monto total negativos (COP)", monto_neg or 0),
        ("Monto total positivos (COP)", monto_pos or 0),
        ("Diferencia neta (COP)", round((monto_pos or 0) - (monto_neg or 0), 2)),
    ]
    for i, (k, v) in enumerate(filas, 1):
        ws.write(i, 0, k, fmt_bold)
        ws.write(i, 1, v)

    # ── Hoja NEGATIVOS SIN CUBRIR ─────────────────────────────────
    ws2 = wb.add_worksheet("NEGATIVOS_SIN_CUBRIR")
    hdrs = [
        "ID_Tx",
        "Tipo",
        "Período",
        "Descripción",
        "Localidad",
        "Monto (COP)",
        "Contraparte posible",
    ]
    for c_, h in enumerate(hdrs):
        ws2.write(0, c_, h, fmt_hdr)
    ws2.set_column("D:D", 35)
    ws2.set_column("G:G", 20)

    # Negativos pendientes — verificar si existe positivo con mismo monto
    cur.execute(
        """
        SELECT t.id_transaccion, t.tipo, t.periodo, t.descripcion, t.localidad,
               ROUND(CAST(t.monto_centavos AS REAL)/100,2)
        FROM transaccion t
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='PENDIENTE' AND t.monto_centavos<0
        ORDER BY t.monto_centavos ASC
    """,
        (id_lote, cuenta),
    )
    neg_rows = cur.fetchall()

    # Montos positivos disponibles para cruce
    cur.execute(
        """
        SELECT DISTINCT ABS(monto_centavos) FROM transaccion
        WHERE id_lote=? AND cuenta_contable=? AND estado_tx='PENDIENTE' AND monto_centavos>0
    """,
        (id_lote, cuenta),
    )
    pos_montos = {r[0] for r in cur.fetchall()}

    for r_, row in enumerate(neg_rows, 1):
        tid, tipo, per, desc, loc, monto = row
        tiene_contra = "Sí" if abs(int(monto * 100)) in pos_montos else "No"
        fmt_bg = fmt_alt if r_ % 2 == 0 else None
        ws2.write(r_, 0, tid, fmt_bg)
        ws2.write(r_, 1, tipo, fmt_bg)
        ws2.write(r_, 2, per, fmt_bg)
        ws2.write(r_, 3, desc, fmt_bg)
        ws2.write(r_, 4, loc, fmt_bg)
        ws2.write(r_, 5, monto, fmt_neg)
        ws2.write(r_, 6, tiene_contra, fmt_bg)
    if neg_rows:
        ws2.autofilter(0, 0, len(neg_rows), 6)

    # ── Hoja POSITIVOS PENDIENTES ─────────────────────────────────
    ws3 = wb.add_worksheet("POSITIVOS_PENDIENTES")
    hdrs3 = ["ID_Tx", "Tipo", "Período", "Descripción", "Localidad", "Monto (COP)"]
    for c_, h in enumerate(hdrs3):
        ws3.write(0, c_, h, fmt_hdr)
    ws3.set_column("D:D", 35)
    cur.execute(
        """
        SELECT id_transaccion, tipo, periodo, descripcion, localidad,
               ROUND(CAST(monto_centavos AS REAL)/100,2)
        FROM transaccion WHERE id_lote=? AND cuenta_contable=? AND estado_tx='PENDIENTE' AND monto_centavos>0
        ORDER BY monto_centavos DESC
    """,
        (id_lote, cuenta),
    )
    for r_, row in enumerate(cur.fetchall(), 1):
        fmt_bg = fmt_alt if r_ % 2 == 0 else None
        tid, tipo, per, desc, loc, monto = row
        ws3.write(r_, 0, tid, fmt_bg)
        ws3.write(r_, 1, tipo, fmt_bg)
        ws3.write(r_, 2, per, fmt_bg)
        ws3.write(r_, 3, desc, fmt_bg)
        ws3.write(r_, 4, loc, fmt_bg)
        ws3.write(r_, 5, monto, fmt_pos)

    # ── Hoja IRRESOLUBLES (negativos sin ningún positivo igual) ───
    ws4 = wb.add_worksheet("IRRESOLUBLES")
    hdrs4 = ["ID_Tx", "Tipo", "Período", "Descripción", "Localidad", "Monto (COP)", "Razón"]
    for c_, h in enumerate(hdrs4):
        ws4.write(0, c_, h, fmt_hdr)
    ws4.set_column("D:D", 35)
    ws4.set_column("G:G", 30)
    cur.execute(
        """
        SELECT t.id_transaccion, t.tipo, t.periodo, t.descripcion, t.localidad,
               ROUND(CAST(t.monto_centavos AS REAL)/100,2), t.monto_centavos
        FROM transaccion t
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='PENDIENTE' AND t.monto_centavos<0
    """,
        (id_lote, cuenta),
    )
    irr = 0
    for row in cur.fetchall():
        tid, tipo, per, desc, loc, monto, mc = row
        if abs(mc) not in pos_montos:
            fmt_bg = fmt_alt if irr % 2 == 0 else None
            ws4.write(irr + 1, 0, tid, fmt_bg)
            ws4.write(irr + 1, 1, tipo, fmt_bg)
            ws4.write(irr + 1, 2, per, fmt_bg)
            ws4.write(irr + 1, 3, desc, fmt_bg)
            ws4.write(irr + 1, 4, loc, fmt_bg)
            ws4.write(irr + 1, 5, monto, fmt_neg)
            ws4.write(irr + 1, 6, "Sin positivo equivalente", fmt_bg)
            irr += 1

    con.close()
    wb.close()
    buf.seek(0)
    fname = f"pendientes_anomalias_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ══════════════════════════════════════════════════════════════════
# REPORTE 4 — Evolución del Motor v1→v4 (PDF)
# Comparativa de tasas + historia de bugs corregidos
# ══════════════════════════════════════════════════════════════════
@report_router.get("/reporte-evolucion-pdf/", tags=["Reportes Especializados"])
async def reporte_evolucion_pdf(id_lote: int = Query(...), cuenta: str = Query(...)):

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    # Historial de todas las ejecuciones para la curva de evolución
    cur.execute(
        """
        SELECT fecha, total, conciliados, tasa FROM historial_ejecucion
        WHERE cuenta=? ORDER BY id ASC
    """,
        (cuenta,),
    )
    historial = cur.fetchall()
    con.close()

    C, S = _pdf_base_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    page_w = A4[0] - 3.6 * cm
    elems = []

    _cabecera_pdf(
        elems,
        page_w,
        "EVOLUCIÓN DEL MOTOR DE CONCILIACIÓN",
        f"Cuenta: {cuenta}  |  Período: {periodo or '—'}  |  {dt.now().strftime('%d/%m/%Y %H:%M')}",
        C,
        S,
    )

    # ── Sección: Versiones del motor ─────────────────────────────
    elems.append(Paragraph("Historia de Versiones y Mejoras", S["seccion"]))
    elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["azul2"], spaceAfter=8))

    versiones = [
        ["Versión", "Tasa", "Fases activas", "Mejora principal"],
        [
            "v1 — Original",
            "~71%",
            "F1, F2, F3, F4",
            "Motor base con coincidencias exactas y subset sum local",
        ],
        [
            "v2 — Bug fixes",
            "~76%",
            "F1, F2, F3, F4, F5",
            "Corrección de 5 bugs críticos. F5 (monto puro) añadida",
        ],
        [
            "v3 — F7 integrada",
            "~86%",
            "F1–F5, F6g, F7, F7b",
            "F7 integrada al pipeline. F5 movida al final. F7b añadida",
        ],
        [
            "v4 — Optimizada",
            "~99%+",
            "F1–F5, F6, F7, F7b",
            "F7b: O(neg×pos×DP) → O(pos×DP). Tiempo: 20min → <1seg",
        ],
    ]
    col_w = [page_w * 0.18, page_w * 0.10, page_w * 0.28, page_w * 0.44]
    rows_v = []
    for i, row in enumerate(versiones):
        if i == 0:
            rows_v.append([Paragraph(f"<b>{c}</b>", S["normal"]) for c in row])
        else:
            color_tasa = (
                C["verde"] if "99" in row[1] else C["azul2"] if "86" in row[1] else C["negro"]
            )
            rows_v.append(
                [
                    Paragraph(row[0], S["bold"]),
                    Paragraph(row[1], S["verde_v"] if "99" in row[1] else S["azul_v"]),
                    Paragraph(row[2], S["small"]),
                    Paragraph(row[3], S["small"]),
                ]
            )
    t_ver = _tabla_std(rows_v, col_w, C["azul"], C["azul_c"], C)
    elems.append(t_ver)
    elems.append(Spacer(1, 16))

    # ── Sección: Bugs corregidos ──────────────────────────────────
    elems.append(Paragraph("Bugs Corregidos (v1 → v4)", S["seccion"]))
    elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["azul2"], spaceAfter=8))

    bugs = [
        ["#", "Versión", "Descripción del bug", "Impacto"],
        [
            "1",
            "v2",
            "F2 no subdividía grupos grandes correctamente",
            "Pérdida de ~3% de conciliaciones",
        ],
        [
            "2",
            "v2",
            "F5 se ejecutaba antes de F6g/F7, consumiendo transacciones",
            "F7 no encontraba candidatos",
        ],
        [
            "3",
            "v2",
            "id_conciliacion negativo causaba JOIN fallido",
            "Grupos F7 no se registraban en DB",
        ],
        ["4", "v2", "UMBRAL_BACKTRACKING muy bajo (5) en F2", "Grupos grandes sin subdividir"],
        ["5", "v2", "F7 no integrada al pipeline principal", "Tasa estancada en 76%"],
        [
            "6",
            "v3",
            "F7b: doble loop O(neg×pos×DP) → timeout >20min",
            "Proceso bloqueado en producción",
        ],
        [
            "7",
            "v4",
            "id_lote hardcodeado (1/2) → datos sobreescritos",
            "Historial de meses perdido",
        ],
        [
            "8",
            "v4",
            "stats-por-fase sin filtro id_lote → datos mezclados",
            "Dashboard mostraba datos incorrectos",
        ],
    ]
    col_b = [page_w * 0.05, page_w * 0.08, page_w * 0.57, page_w * 0.30]
    rows_b = []
    for i, row in enumerate(bugs):
        if i == 0:
            rows_b.append([Paragraph(f"<b>{c}</b>", S["normal"]) for c in row])
        else:
            rows_b.append(
                [
                    Paragraph(row[0], S["center"]),
                    Paragraph(row[1], S["bold"]),
                    Paragraph(row[2], S["small"]),
                    Paragraph(row[3], S["rojo_v"]),
                ]
            )
    t_bugs = _tabla_std(rows_b, col_b, C["rojo"], C["rojo_c"], C)
    elems.append(t_bugs)
    elems.append(Spacer(1, 16))

    # ── Sección: Historial de ejecuciones reales ──────────────────
    if historial:
        elems.append(Paragraph("Historial de Ejecuciones Reales", S["seccion"]))
        elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["verde"], spaceAfter=8))
        col_h = [page_w * 0.25, page_w * 0.18, page_w * 0.18, page_w * 0.18, page_w * 0.21]
        rows_h = [
            [
                Paragraph(f"<b>{h}</b>", S["normal"])
                for h in ["Fecha", "Total", "Conciliados", "Pendientes", "Efectividad"]
            ]
        ]
        for fecha, tot, con_, tas in historial:
            pen_ = (tot or 0) - (con_ or 0)
            rows_h.append(
                [
                    Paragraph(str(fecha or ""), S["small"]),
                    Paragraph(f"{(tot or 0):,}", S["normal"]),
                    Paragraph(f"{(con_ or 0):,}", S["verde_v"]),
                    Paragraph(f"{pen_:,}", S["rojo_v"]),
                    Paragraph(f"{(tas or 0):.1f}%", S["azul_v"]),
                ]
            )
        t_hist = _tabla_std(rows_h, col_h, C["verde"], C["verde_c"], C)
        elems.append(t_hist)
        elems.append(Spacer(1, 16))

    # ── Sección: Estado actual ────────────────────────────────────
    elems.append(Paragraph("Estado Actual del Motor", S["seccion"]))
    elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["verde"], spaceAfter=8))
    estado_data = [
        [Paragraph("<b>Métrica</b>", S["normal"]), Paragraph("<b>Valor</b>", S["normal"])],
        [Paragraph("Versión activa", S["normal"]), Paragraph("v4 — Optimizada", S["bold"])],
        [
            Paragraph("Fases del motor", S["normal"]),
            Paragraph("F1 → F2 → F3 → F4 → F6 → F7 → F7b → F5", S["small"]),
        ],
        [Paragraph("Tasa actual", S["normal"]), Paragraph(f"{tasa:.1f}%", S["verde_v"])],
        [Paragraph("Registros procesados", S["normal"]), Paragraph(f"{total:,}", S["bold"])],
        [Paragraph("Conciliados", S["normal"]), Paragraph(f"{conci:,}", S["verde_v"])],
        [Paragraph("Pendientes", S["normal"]), Paragraph(f"{pend:,}", S["rojo_v"])],
        [
            Paragraph("Tiempo F7b (v3 vs v4)", S["normal"]),
            Paragraph(">20 minutos → <1 segundo", S["bold"]),
        ],
    ]
    t_est = _tabla_std(estado_data, [page_w * 0.45, page_w * 0.55], C["azul"], C["gris_c"], C)
    elems.append(t_est)

    _pie_pdf(elems, page_w, f"evolucion_motor_{cuenta}.pdf", C, S)
    doc.build(elems)
    buf.seek(0)
    fname = f"evolucion_motor_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ══════════════════════════════════════════════════════════════════
# PDFs de los reportes 1, 2 y 3
# ══════════════════════════════════════════════════════════════════
@report_router.get("/reporte-conciliacion-completa-pdf/", tags=["Reportes Especializados"])
async def reporte_conciliacion_completa_pdf(id_lote: int = Query(...), cuenta: str = Query(...)):
    """PDF del reporte de conciliación completa con todas las fases."""

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    C, S = _pdf_base_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    page_w = A4[0] - 3.6 * cm
    elems = []

    _cabecera_pdf(
        elems,
        page_w,
        "CONCILIACIÓN COMPLETA — LOGRADO POR FASE",
        f"Cuenta: {cuenta}  |  Período: {periodo or '—'}  |  {dt.now().strftime('%d/%m/%Y %H:%M')}",
        C,
        S,
    )

    # KPIs
    kpi_rows = [
        [
            Paragraph(f"<b>{total:,}</b><br/>Total", S["center"]),
            Paragraph(f"<b>{conci:,}</b><br/>Conciliados", S["verde_v"]),
            Paragraph(f"<b>{pend:,}</b><br/>Pendientes", S["rojo_v"]),
            Paragraph(f"<b>{tasa:.1f}%</b><br/>Efectividad", S["azul_v"]),
        ]
    ]
    t_kpi = Table(kpi_rows, colWidths=[page_w / 4] * 4)
    t_kpi.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), C["gris_c"]),
                ("BACKGROUND", (1, 0), (1, -1), C["verde_c"]),
                ("BACKGROUND", (2, 0), (2, -1), C["rojo_c"]),
                ("BACKGROUND", (3, 0), (3, -1), C["azul_c"]),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, C["borde"]),
            ]
        )
    )
    elems.append(t_kpi)
    elems.append(Spacer(1, 14))

    # Desglose por fase
    elems.append(Paragraph("Desglose por Fase", S["seccion"]))
    elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["azul2"], spaceAfter=8))
    FASE_DESC = {
        "F1": "Fast-Pass — 1:1 exacto",
        "F2": "Subset Sum — N:N suma cero",
        "F3": "Tolerancia ±5 cts",
        "F4": "Localidad — monto+localidad",
        "F5": "Monto Puro Global",
        "F6": "Subset Sum Global (N pos → 1 neg)",
        "F7": "Final Cleaning (1 pos → N neg)",
        "F7b": "Final Cleaning B",
    }
    cur.execute(
        """
        SELECT CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
               COUNT(DISTINCT ABS(t.id_conciliacion)), COUNT(t.id_transaccion)
        FROM transaccion t JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
        GROUP BY fase ORDER BY fase
    """,
        (id_lote, cuenta),
    )
    fase_rows = [
        [
            Paragraph(f"<b>{h}</b>", S["normal"])
            for h in ["Fase", "Descripción", "Grupos", "Transacciones", "% Conciliados"]
        ]
    ]
    for fase, grupos, txs in cur.fetchall():
        pct = round(txs / conci * 100, 1) if conci else 0
        fase_rows.append(
            [
                Paragraph(f"<b>{fase}</b>", S["bold"]),
                Paragraph(FASE_DESC.get(fase, fase), S["small"]),
                Paragraph(f"{grupos:,}", S["normal"]),
                Paragraph(f"{txs:,}", S["normal"]),
                Paragraph(f"{pct}%", S["verde_v"]),
            ]
        )
    t_fases = _tabla_std(
        fase_rows,
        [page_w * 0.07, page_w * 0.48, page_w * 0.12, page_w * 0.15, page_w * 0.18],
        C["azul"],
        C["azul_c"],
        C,
    )
    elems.append(t_fases)

    con.close()
    _pie_pdf(elems, page_w, f"conciliacion_completa_{cuenta}.pdf", C, S)
    doc.build(elems)
    buf.seek(0)
    fname = f"conciliacion_completa_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@report_router.get("/reporte-metricas-fases-pdf/", tags=["Reportes Especializados"])
async def reporte_metricas_fases_pdf(id_lote: int = Query(...), cuenta: str = Query(...)):
    """PDF de métricas por fase con grupos y cobertura de negativos."""

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    C, S = _pdf_base_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    page_w = A4[0] - 3.6 * cm
    elems = []

    _cabecera_pdf(
        elems,
        page_w,
        "MÉTRICAS POR FASE (F1–F7b)",
        f"Cuenta: {cuenta}  |  Período: {periodo or '—'}  |  {dt.now().strftime('%d/%m/%Y %H:%M')}",
        C,
        S,
    )

    elems.append(Paragraph("Métricas Detalladas por Fase", S["seccion"]))
    elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["azul2"], spaceAfter=8))

    cur.execute(
        """
        SELECT CASE WHEN c.fase_origen='F6g' THEN 'F6' ELSE c.fase_origen END AS fase,
               COUNT(DISTINCT ABS(t.id_conciliacion)) AS grupos,
               COUNT(t.id_transaccion) AS txs,
               SUM(CASE WHEN t.monto_centavos<0 THEN 1 ELSE 0 END) AS neg,
               SUM(CASE WHEN t.monto_centavos>0 THEN 1 ELSE 0 END) AS pos,
               ROUND(SUM(ABS(CAST(t.monto_centavos AS REAL)/100)),2) AS monto
        FROM transaccion t JOIN conciliacion c ON ABS(t.id_conciliacion)=c.id_conciliacion
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='CONCILIADO'
        GROUP BY fase ORDER BY fase
    """,
        (id_lote, cuenta),
    )
    hdrs = [
        "Fase",
        "Grupos",
        "Transacciones",
        "Negativos",
        "Positivos",
        "Monto (COP)",
        "% Total",
        "% Conciliados",
    ]
    rows = [[Paragraph(f"<b>{h}</b>", S["normal"]) for h in hdrs]]
    for fase, grupos, txs, neg, pos, monto in cur.fetchall():
        pct_t = round(txs / total * 100, 1) if total else 0
        pct_c = round(txs / conci * 100, 1) if conci else 0
        rows.append(
            [
                Paragraph(f"<b>{fase}</b>", S["bold"]),
                Paragraph(f"{grupos:,}", S["normal"]),
                Paragraph(f"{txs:,}", S["normal"]),
                Paragraph(f"{neg:,}", S["rojo_v"]),
                Paragraph(f"{pos:,}", S["verde_v"]),
                Paragraph(f"${monto:,.0f}", S["normal"]),
                Paragraph(f"{pct_t}%", S["normal"]),
                Paragraph(f"{pct_c}%", S["azul_v"]),
            ]
        )
    col_w = [page_w * 0.07] + [page_w * 0.12] * 5 + [page_w * 0.10, page_w * 0.12]
    t = _tabla_std(rows, col_w, C["azul"], C["azul_c"], C)
    elems.append(t)

    con.close()
    _pie_pdf(elems, page_w, f"metricas_fases_{cuenta}.pdf", C, S)
    doc.build(elems)
    buf.seek(0)
    fname = f"metricas_fases_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@report_router.get("/reporte-pendientes-pdf/", tags=["Reportes Especializados"])
async def reporte_pendientes_pdf(id_lote: int = Query(...), cuenta: str = Query(...)):
    """PDF de pendientes y anomalías con análisis de irresolubles."""

    con = sq3.connect(DB_PATH)
    cur = con.cursor()
    total, conci, pend, tasa, periodo = _get_lote_info(cur, id_lote, cuenta)

    C, S = _pdf_base_styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    page_w = A4[0] - 3.6 * cm
    elems = []

    _cabecera_pdf(
        elems,
        page_w,
        "PENDIENTES Y ANOMALÍAS",
        f"Cuenta: {cuenta}  |  Período: {periodo or '—'}  |  {dt.now().strftime('%d/%m/%Y %H:%M')}",
        C,
        S,
    )

    cur.execute(
        """
        SELECT COUNT(*),
               SUM(CASE WHEN monto_centavos<0 THEN 1 ELSE 0 END),
               SUM(CASE WHEN monto_centavos>0 THEN 1 ELSE 0 END),
               ROUND(SUM(CASE WHEN monto_centavos<0 THEN ABS(CAST(monto_centavos AS REAL)/100) ELSE 0 END),2),
               ROUND(SUM(CASE WHEN monto_centavos>0 THEN CAST(monto_centavos AS REAL)/100 ELSE 0 END),2)
        FROM transaccion WHERE id_lote=? AND cuenta_contable=? AND estado_tx='PENDIENTE'
    """,
        (id_lote, cuenta),
    )
    r = cur.fetchone()
    tot_p, neg_p, pos_p, monto_neg, monto_pos = r

    elems.append(Paragraph("Resumen de Pendientes", S["seccion"]))
    elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["naranja"], spaceAfter=8))
    res_rows = [
        [Paragraph("<b>Concepto</b>", S["normal"]), Paragraph("<b>Valor</b>", S["normal"])],
        [Paragraph("Total pendientes", S["normal"]), Paragraph(f"{tot_p or 0:,}", S["bold"])],
        [Paragraph("Negativos pendientes", S["normal"]), Paragraph(f"{neg_p or 0:,}", S["rojo_v"])],
        [
            Paragraph("Positivos pendientes", S["normal"]),
            Paragraph(f"{pos_p or 0:,}", S["verde_v"]),
        ],
        [
            Paragraph("Monto negativos (COP)", S["normal"]),
            Paragraph(f"${monto_neg or 0:,.2f}", S["rojo_v"]),
        ],
        [
            Paragraph("Monto positivos (COP)", S["normal"]),
            Paragraph(f"${monto_pos or 0:,.2f}", S["verde_v"]),
        ],
        [
            Paragraph("Diferencia neta (COP)", S["normal"]),
            Paragraph(f"${(monto_pos or 0)-(monto_neg or 0):,.2f}", S["bold"]),
        ],
    ]
    t_res = _tabla_std(res_rows, [page_w * 0.55, page_w * 0.45], C["naranja"], C["nar_c"], C)
    elems.append(t_res)
    elems.append(Spacer(1, 14))

    # Top 30 negativos sin cubrir
    cur.execute(
        """
        SELECT t.id_transaccion, t.tipo, t.periodo, t.descripcion, t.localidad,
               ROUND(CAST(t.monto_centavos AS REAL)/100,2)
        FROM transaccion t
        WHERE t.id_lote=? AND t.cuenta_contable=? AND t.estado_tx='PENDIENTE' AND t.monto_centavos<0
        ORDER BY t.monto_centavos ASC LIMIT 30
    """,
        (id_lote, cuenta),
    )
    neg_rows = cur.fetchall()
    if neg_rows:
        elems.append(
            Paragraph(f"Top {len(neg_rows)} Negativos Pendientes (mayor monto)", S["seccion"])
        )
        elems.append(HRFlowable(width=page_w, thickness=1.5, color=C["rojo"], spaceAfter=8))
        hdrs = ["ID", "Tipo", "Período", "Descripción", "Localidad", "Monto (COP)"]
        rows = [[Paragraph(f"<b>{h}</b>", S["normal"]) for h in hdrs]]
        for tid, tipo, per, desc, loc, monto in neg_rows:
            rows.append(
                [
                    Paragraph(str(tid), S["small"]),
                    Paragraph(str(tipo or ""), S["small"]),
                    Paragraph(str(per or ""), S["small"]),
                    Paragraph(str(desc or "")[:55], S["small"]),
                    Paragraph(str(loc or ""), S["small"]),
                    Paragraph(f"${monto:,.2f}", S["rojo_v"]),
                ]
            )
        col_w = [
            page_w * 0.08,
            page_w * 0.07,
            page_w * 0.10,
            page_w * 0.45,
            page_w * 0.12,
            page_w * 0.18,
        ]
        t = _tabla_std(rows, col_w, C["rojo"], C["rojo_c"], C)
        elems.append(t)

    con.close()
    _pie_pdf(elems, page_w, f"pendientes_anomalias_{cuenta}.pdf", C, S)
    doc.build(elems)
    buf.seek(0)
    fname = f"pendientes_anomalias_{cuenta}_{dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
