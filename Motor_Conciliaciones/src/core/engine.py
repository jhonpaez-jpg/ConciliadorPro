import polars as pl
from src.core.models import Transaccion

UMBRAL_BACKTRACKING = 20


def _subset_sum_dp(objetivo: int, negativos: list[tuple]) -> list[tuple] | None:
    target_abs = abs(objetivo)
    negs_abs = [(i, abs(m)) for i, m in negativos]
    dp = {0: []}
    for id_n, abs_m in negs_abs:
        nuevos = {}
        for suma_actual, items in dp.items():
            nueva_suma = suma_actual + abs_m
            if nueva_suma <= target_abs and nueva_suma not in dp:
                nuevos[nueva_suma] = items + [(id_n, -abs_m)]
        dp.update(nuevos)
        if target_abs in dp:
            break
    return dp.get(target_abs, None)


class ReconciliationEngine:
    """
    Motor de Conciliación Contable
    Criterio: N.º diario + Localidad → registros deben sumar cero.
    F1 — 1:1 exacto por n_diario + localidad
    F2 — N:N grupos suma cero por n_diario + localidad
    F3 — Fuzzy ±5 centavos por n_diario + localidad
    F4 — Parejas exactas monto + localidad (sin n_diario)
    F5 — Parejas exactas solo por monto (sin localidad ni n_diario)
    """

    def __init__(self):
        self.conciliadas                = []
        self.pendientes                 = []
        self.pendientes_con_contraparte = []
        self.pendientes_sin_contraparte = []
        self.tasa_real                  = 0.0
        self.tasa_global                = 0.0

    def ejecutar_proceso_completo(self, transacciones_list: list[Transaccion]):
        total = len(transacciones_list)
        print(f"🚀 Motor activado: {total} registros.")

        lookup: dict[int, Transaccion] = {t.id_transaccion: t for t in transacciones_list}

        df = pl.DataFrame({
            "id":        [t.id_transaccion for t in transacciones_list],
            "monto":     [t.monto_centavos for t in transacciones_list],
            "n_diario":  [t.n_diario       for t in transacciones_list],
            "localidad": [t.localidad      for t in transacciones_list],
        })

        ids_conciliados: set[int] = set()
        # Cada entrada: {"fase": "F1", "grupo": [Transaccion, ...]}
        resultado_final: list[dict] = []

        # ── FASE 1 — Parejas exactas 1:1 ─────────────────────────
        print("🔍 F1: Parejas exactas 1:1...")
        pos = df.filter(pl.col("monto") > 0)
        neg = (
            df.filter(pl.col("monto") < 0)
            .with_columns((pl.col("monto") * -1).alias("monto_abs"))
            .rename({"id": "id_neg"})
            .select(["id_neg", "n_diario", "localidad", "monto_abs"])
        )
        matches_f1 = (
            pos.join(neg, on=["n_diario", "localidad"], how="inner")
            .filter(pl.col("monto") == pl.col("monto_abs"))
            .select(["id", "id_neg"])
            .unique(subset=["id"])
            .unique(subset=["id_neg"])
        )
        for id_pos, id_neg in matches_f1.iter_rows():
            if id_pos not in ids_conciliados and id_neg not in ids_conciliados:
                resultado_final.append({"fase": "F1", "grupo": [lookup[id_pos], lookup[id_neg]]})
                ids_conciliados.add(id_pos)
                ids_conciliados.add(id_neg)
        print(f"   ✅ F1: {len(resultado_final)} grupos.")

        # ── FASE 2 — Grupos N:N suma cero ────────────────────────
        print("🔍 F2: Grupos N:N suma cero...")
        df_r = df.filter(~pl.col("id").is_in(ids_conciliados))
        f2_inicio = len(resultado_final)
        grupos_sin_subdividir = 0

        if not df_r.is_empty():
            grupos_en_cero = (
                df_r.group_by(["n_diario", "localidad"])
                .agg(pl.sum("monto").alias("suma_total"))
                .filter(pl.col("suma_total") == 0)
                .select(["n_diario", "localidad"])
            )
            if not grupos_en_cero.is_empty():
                ids_por_grupo = (
                    df_r.join(grupos_en_cero, on=["n_diario", "localidad"], how="inner")
                    .group_by(["n_diario", "localidad"])
                    .agg(pl.col("id").alias("ids_grupo"))
                )
                for row in ids_por_grupo.iter_rows(named=True):
                    nuevos = [i for i in row["ids_grupo"] if i not in ids_conciliados]
                    if not nuevos:
                        continue
                    positivos = [(i, lookup[i].monto_centavos) for i in nuevos if lookup[i].monto_centavos > 0]
                    negativos = [(i, lookup[i].monto_centavos) for i in nuevos if lookup[i].monto_centavos < 0]
                    if not positivos or not negativos:
                        continue

                    if len(positivos) == 1:
                        resultado_final.append({"fase": "F2", "grupo": [lookup[i] for i in nuevos]})
                        ids_conciliados.update(nuevos)
                    elif len(negativos) <= UMBRAL_BACKTRACKING:
                        neg_disponibles = list(negativos)
                        subdividido = False
                        for id_pos, monto_pos in sorted(positivos, key=lambda x: x[1], reverse=True):
                            combo = _subset_sum_dp(monto_pos, neg_disponibles)
                            if combo is not None:
                                sg = [id_pos] + [id_n for id_n, _ in combo]
                                resultado_final.append({"fase": "F2", "grupo": [lookup[i] for i in sg]})
                                ids_conciliados.update(sg)
                                for item in combo:
                                    neg_disponibles.remove(item)
                                subdividido = True
                        if not subdividido:
                            resultado_final.append({"fase": "F2", "grupo": [lookup[i] for i in nuevos]})
                            ids_conciliados.update(nuevos)
                    else:
                        grupos_sin_subdividir += 1
                        resultado_final.append({"fase": "F2", "grupo": [lookup[i] for i in nuevos]})
                        ids_conciliados.update(nuevos)

        print(f"   ✅ F2: {len(resultado_final) - f2_inicio} grupos nuevos (total: {len(resultado_final)}).")
        if grupos_sin_subdividir:
            print(f"   ℹ️  {grupos_sin_subdividir} grupos grandes conciliados completos.")

        # ── FASE 3 — Tolerancia ±5 centavos ──────────────────────
        print("🔍 F3: Tolerancia ±5 centavos...")
        TOLERANCIA = 5
        df_r = df.filter(~pl.col("id").is_in(ids_conciliados))
        f3_inicio = len(resultado_final)
        if not df_r.is_empty():
            grupos_fuzzy = (
                df_r.group_by(["n_diario", "localidad"])
                .agg([pl.sum("monto").alias("suma_total"), pl.col("id").alias("ids_grupo")])
                .filter((pl.col("suma_total").abs() <= TOLERANCIA) & (pl.col("suma_total") != 0))
            )
            for row in grupos_fuzzy.iter_rows(named=True):
                nuevos = [i for i in row["ids_grupo"] if i not in ids_conciliados]
                if nuevos:
                    resultado_final.append({"fase": "F3", "grupo": [lookup[i] for i in nuevos]})
                    ids_conciliados.update(nuevos)
        print(f"   ✅ F3: {len(resultado_final) - f3_inicio} grupos nuevos (total: {len(resultado_final)}).")

        # ── FASE 4 — Parejas exactas por monto+localidad (sin n_diario) ──
        print("🔍 F4: Parejas exactas monto+localidad (sin n_diario)...")
        df_r = df.filter(~pl.col("id").is_in(ids_conciliados))
        f4_inicio = len(resultado_final)

        if not df_r.is_empty():
            pos4 = df_r.filter(pl.col("monto") > 0)
            neg4 = (
                df_r.filter(pl.col("monto") < 0)
                .with_columns((pl.col("monto") * -1).alias("monto_abs"))
                .rename({"id": "id_neg"})
                .select(["id_neg", "localidad", "monto_abs"])
            )
            matches_f4 = (
                pos4.join(neg4, left_on=["localidad", "monto"],
                               right_on=["localidad", "monto_abs"], how="inner")
                .select(["id", "id_neg"])
                .unique(subset=["id"])
                .unique(subset=["id_neg"])
            )
            for id_pos, id_neg in matches_f4.iter_rows():
                if id_pos not in ids_conciliados and id_neg not in ids_conciliados:
                    resultado_final.append({"fase": "F4", "grupo": [lookup[id_pos], lookup[id_neg]]})
                    ids_conciliados.add(id_pos)
                    ids_conciliados.add(id_neg)

        print(f"   ✅ F4: {len(resultado_final) - f4_inicio} grupos nuevos (total: {len(resultado_final)}).")

        # ── FASE 5 — Parejas exactas solo por monto (procesado por lotes) ──
        print("🔍 F5: Parejas exactas solo por monto global (por lotes)...")
        f5_inicio = len(resultado_final)

        # Construir índices en Python puro — sin join masivo en polars
        pendientes_f5 = [t for t in transacciones_list if t.id_transaccion not in ids_conciliados]

        from collections import defaultdict as _dd
        pos_pool: dict = _dd(list)
        neg_pool: dict = _dd(list)
        for t in pendientes_f5:
            if t.monto_centavos > 0:
                pos_pool[t.monto_centavos].append(t.id_transaccion)
            elif t.monto_centavos < 0:
                neg_pool[abs(t.monto_centavos)].append(t.id_transaccion)

        # Iterar solo los montos que tienen contraparte — O(montos únicos)
        for monto in list(pos_pool.keys()):
            if monto not in neg_pool:
                continue
            while pos_pool[monto] and neg_pool[monto]:
                id_pos = pos_pool[monto].pop(0)
                id_neg = neg_pool[monto].pop(0)
                if id_pos not in ids_conciliados and id_neg not in ids_conciliados:
                    resultado_final.append({"fase": "F5", "grupo": [lookup[id_pos], lookup[id_neg]]})
                    ids_conciliados.add(id_pos)
                    ids_conciliados.add(id_neg)

        del pos_pool, neg_pool, pendientes_f5
        print(f"   ✅ F5: {len(resultado_final) - f5_inicio} grupos nuevos (total: {len(resultado_final)}).")

        # ── CIERRE — clasificar pendientes y calcular tasa real ──
        pendientes_todos = [t for t in transacciones_list if t.id_transaccion not in ids_conciliados]

        if pendientes_todos:
            df_pend = pl.DataFrame({
                "id":        [t.id_transaccion for t in pendientes_todos],
                "monto":     [t.monto_centavos for t in pendientes_todos],
                "n_diario":  [t.n_diario       for t in pendientes_todos],
                "localidad": [t.localidad      for t in pendientes_todos],
            })
            grupos_mixtos = (
                df_pend.group_by(["n_diario", "localidad"])
                .agg([
                    (pl.col("monto") > 0).sum().alias("n_pos"),
                    (pl.col("monto") < 0).sum().alias("n_neg"),
                ])
                .filter((pl.col("n_pos") > 0) & (pl.col("n_neg") > 0))
                .select(["n_diario", "localidad"])
            )
            ids_con_contraparte = set(
                df_pend.join(grupos_mixtos, on=["n_diario", "localidad"], how="inner")["id"].to_list()
            )
            pend_con = [t for t in pendientes_todos if t.id_transaccion in ids_con_contraparte]
            pend_sin = [t for t in pendientes_todos if t.id_transaccion not in ids_con_contraparte]
        else:
            pend_con = []
            pend_sin = []

        universo_real = len(ids_conciliados) + len(pend_con)
        tasa_real     = (len(ids_conciliados) / universo_real * 100) if universo_real else 100.0
        tasa_global   = (len(ids_conciliados) / total * 100) if total else 0.0

        self.conciliadas                = resultado_final
        self.pendientes                 = pendientes_todos
        self.pendientes_con_contraparte = pend_con
        self.pendientes_sin_contraparte = pend_sin
        self.tasa_real                  = tasa_real
        self.tasa_global                = tasa_global

        print(f"\n{'='*50}")
        print(f"✅ Motor completado.")
        print(f"   Grupos conciliados        : {len(self.conciliadas)}")
        print(f"   Registros conciliados     : {len(ids_conciliados):,} / {total:,}")
        print(f"   Pendientes con contraparte: {len(pend_con):,}")
        print(f"   Pendientes sin contraparte: {len(pend_sin):,}")
        print(f"   Tasa real del motor       : {tasa_real:.1f}%")
        print(f"   Tasa global               : {tasa_global:.1f}%")
        print(f"{'='*50}\n")

        return self.conciliadas, self.pendientes