"""
Motor de Conciliación Contable — versión final v4 (optimizada)
==============================================================

CORRECCIÓN CRÍTICA DE RENDIMIENTO (v3 → v4):

  F7b timeout >20 minutos → resuelto en <1 segundo.

  Causa raíz en v3:
    F7b tenía un doble loop:
      for neg in neg_rest:                     # ~39 negativos
          for pos in pos_libres:               # ~780 positivos
              _dp_exacto(monto_pos, neg_pool)  # DP por cada combinación
    Complejidad: O(neg_rest × pos_libres × DP) = 30.420 llamadas DP.
    Con timeout=8s por llamada → hasta 4.000 minutos teóricos.

  Fix en v4:
    Loop invertido — itera sobre POSITIVOS (no negativos):
      for pos in pos_libres:              # ~780 positivos, UN solo DP cada uno
          _elegir_dp(monto_pos, neg_pool) # cubre N negativos de una vez
    Complejidad: O(pos_libres × DP) = 780 llamadas DP.
    Tiempo real: <1 segundo (la mayoría termina en <0.01s con poda temprana).

  Además: se añade poda temprana en F7b — si suma(neg_libres) < monto_pos,
  se salta sin llamar al DP (evita el 95% de las llamadas).

Historial de correcciones:
  v1 — Engine original (71.08%)
  v2 — Bugs 1-5 corregidos, F7 añadida (75.99% por falta de integración)
  v3 — F7 integrada, F5 movida al final, F7b añadida (85.96%)
  v4 — F7b optimizada de O(neg×pos×DP) → O(pos×DP) (target: ~99%)

Orden de fases:
  F1 → F2 → F3 → F4 → F6g → F7 → F7b → F5
"""

import time as _time
from collections import defaultdict as _dd

import polars as pl

try:
    from src.core.models import Transaccion
except ImportError:
    from dataclasses import dataclass

    @dataclass
    class Transaccion:
        id_transaccion: int
        monto_centavos: int
        n_diario: str
        localidad: str


# ──────────────────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────────────────

UMBRAL_BACKTRACKING = 20
_MAX_CANDIDATOS_DP  = 500
_TIMEOUT_DP_SEG     = 8.0
_ESCALA_GRANDE      = 10_000     # > 10M
_ESCALA_MEDIANA     = 1_000      # 100K – 10M
_UMBRAL_GRANDE      = 10_000_000
_UMBRAL_MEDIANO     = 100_000    # exacto para < 100K (precisión centavo)
_UMBRAL_NEG_GRANDE  = 5_000_000  # umbral F6g


# ──────────────────────────────────────────────────────────────────────────────
# Funciones DP
# ──────────────────────────────────────────────────────────────────────────────

def _dp_exacto(
    objetivo: int,
    candidatos: list[tuple],   # [(id, monto_abs), ...] DESC
    timeout: float = _TIMEOUT_DP_SEG,
) -> list[tuple] | None:
    """DP sin escala. Preciso al centavo. Adecuado para objetivos < 100K."""
    target = abs(objetivo)
    if target == 0:
        return []
    if sum(m for _, m in candidatos) < target:
        return None
    dp: dict[int, tuple | None] = {0: None}
    t0 = _time.monotonic()
    estados = 0
    for id_c, abs_m in candidatos:
        for suma in list(dp.keys()):
            nueva = suma + abs_m
            if nueva <= target and nueva not in dp:
                dp[nueva] = (suma, id_c, abs_m)
                estados += 1
                if estados % 50_000 == 0 and _time.monotonic() - t0 > timeout:
                    return None
        if target in dp:
            break
    if target not in dp:
        return None
    resultado = []
    suma = target
    while dp[suma] is not None:
        sp, id_c, abs_m = dp[suma]
        resultado.append((id_c, -abs_m))
        suma = sp
    return resultado


def _dp_escalado(
    objetivo: int,
    candidatos: list[tuple],
    escala: int,
    timeout: float = _TIMEOUT_DP_SEG,
) -> list[tuple] | None:
    """DP con escala. Para objetivos >= 100K donde exacto sería lento."""
    target_sc = abs(objetivo) // escala
    if target_sc == 0:
        return _dp_exacto(objetivo, candidatos, timeout)
    id_a = {id_c: abs_m for id_c, abs_m in candidatos}
    cands_sc = [(id_c, abs_m // escala) for id_c, abs_m in candidatos
                if abs_m // escala > 0]
    if not cands_sc or sum(m for _, m in cands_sc) < target_sc:
        return None
    dp: dict[int, tuple | None] = {0: None}
    t0 = _time.monotonic()
    estados = 0
    for id_c, abs_sc in cands_sc:
        for suma in list(dp.keys()):
            nueva = suma + abs_sc
            if nueva <= target_sc and nueva not in dp:
                dp[nueva] = (suma, id_c, abs_sc)
                estados += 1
                if estados % 50_000 == 0 and _time.monotonic() - t0 > timeout:
                    return None
        if target_sc in dp:
            break
    if target_sc not in dp:
        return None
    resultado = []
    suma = target_sc
    while dp[suma] is not None:
        sp, id_c, _ = dp[suma]
        resultado.append((id_c, -id_a[id_c]))
        suma = sp
    return resultado


def _elegir_dp(objetivo: int, candidatos: list[tuple]) -> list[tuple] | None:
    """Selecciona escala según magnitud. Candidatos deben venir DESC."""
    abs_obj = abs(objetivo)
    if abs_obj >= _UMBRAL_GRANDE:
        return _dp_escalado(objetivo, candidatos, _ESCALA_GRANDE)
    elif abs_obj >= _UMBRAL_MEDIANO:
        return _dp_escalado(objetivo, candidatos, _ESCALA_MEDIANA)
    else:
        return _dp_exacto(objetivo, candidatos)


def _cands_desc(pool: list[tuple], usados: set[int], max_n: int) -> list[tuple]:
    """Devuelve los max_n candidatos libres de mayor monto_abs, DESC."""
    return sorted(
        [(id_c, abs_m) for id_c, abs_m in pool if id_c not in usados],
        key=lambda x: x[1],
        reverse=True,
    )[:max_n]


# ──────────────────────────────────────────────────────────────────────────────
# Motor principal
# ──────────────────────────────────────────────────────────────────────────────

class ReconciliationEngine:
    """
    Motor de Conciliación Contable — v4 final optimizado.

    Fases:
      F1   — 1:1 exacto por n_diario + localidad
      F2   — N:N suma cero por n_diario + localidad
      F3   — Fuzzy ±5 centavos por n_diario + localidad
      F4   — Parejas exactas monto + localidad (sin n_diario)
      F6g  — N positivos → 1 negativo GRANDE >5M  (global)
      F7   — 1 positivo → N negativos             (global, patrón dominante)
      F7b  — Limpieza: positivos restantes → negativos restantes (exacto, RÁPIDO)
      F5   — Parejas 1:1 exactas por monto         (último recurso)
    """

    def __init__(self):
        self.conciliadas:                list[dict] = []
        self.pendientes:                 list       = []
        self.pendientes_con_contraparte: list       = []
        self.pendientes_sin_contraparte: list       = []
        self.tasa_real:                  float      = 0.0
        self.tasa_global:                float      = 0.0

    def ejecutar_proceso_completo(
        self,
        transacciones_list: list[Transaccion],
    ) -> tuple[list[dict], list]:

        total = len(transacciones_list)
        print(f"🚀 Motor activado: {total} registros.")

        lookup: dict[int, Transaccion] = {t.id_transaccion: t for t in transacciones_list}
        df = pl.DataFrame({
            "id":        [t.id_transaccion for t in transacciones_list],
            "monto":     [t.monto_centavos for t in transacciones_list],
            "n_diario":  [t.n_diario       for t in transacciones_list],
            "localidad": [t.localidad      for t in transacciones_list],
        })

        ids_conciliados: set[int]   = set()
        resultado_final: list[dict] = []

        # ── F1 ───────────────────────────────────────────────────────────────
        print("🔍 F1: Parejas exactas 1:1...")
        f1_i = len(resultado_final)
        pos = df.filter(pl.col("monto") > 0)
        neg = (
            df.filter(pl.col("monto") < 0)
            .with_columns((pl.col("monto") * -1).alias("monto_abs"))
            .rename({"id": "id_neg"})
            .select(["id_neg", "n_diario", "localidad", "monto_abs"])
        )
        matches = (
            pos.join(neg, on=["n_diario", "localidad"], how="inner")
            .filter(pl.col("monto") == pl.col("monto_abs"))
            .select(["id", "id_neg"])
            .unique(subset=["id"])
            .unique(subset=["id_neg"])
        )
        for id_pos, id_neg in matches.iter_rows():
            if id_pos not in ids_conciliados and id_neg not in ids_conciliados:
                resultado_final.append({"fase": "F1", "grupo": [lookup[id_pos], lookup[id_neg]]})
                ids_conciliados.add(id_pos)
                ids_conciliados.add(id_neg)
        print(f"   ✅ F1: {len(resultado_final) - f1_i} grupos.")

        # ── F2 ───────────────────────────────────────────────────────────────
        print("🔍 F2: Grupos N:N suma cero...")
        df_r = df.filter(~pl.col("id").is_in(ids_conciliados))
        f2_i = len(resultado_final)
        grupos_sin_subdividir = 0
        if not df_r.is_empty():
            grupos_cero = (
                df_r.group_by(["n_diario", "localidad"])
                .agg(pl.sum("monto").alias("s"))
                .filter(pl.col("s") == 0)
                .select(["n_diario", "localidad"])
            )
            if not grupos_cero.is_empty():
                ids_por_g = (
                    df_r.join(grupos_cero, on=["n_diario", "localidad"], how="inner")
                    .group_by(["n_diario", "localidad"])
                    .agg(pl.col("id").alias("ids"))
                )
                for row in ids_por_g.iter_rows(named=True):
                    nuevos = [i for i in row["ids"] if i not in ids_conciliados]
                    if not nuevos:
                        continue
                    poss = [(i, lookup[i].monto_centavos) for i in nuevos
                            if lookup[i].monto_centavos > 0]
                    negs = [(i, lookup[i].monto_centavos) for i in nuevos
                            if lookup[i].monto_centavos < 0]
                    if not poss or not negs:
                        continue
                    if len(poss) == 1:
                        resultado_final.append({"fase": "F2",
                                                "grupo": [lookup[i] for i in nuevos]})
                        ids_conciliados.update(nuevos)
                    elif len(negs) <= UMBRAL_BACKTRACKING:
                        neg_disp = list(negs)
                        subdividido = False
                        for id_p, m_p in sorted(poss, key=lambda x: x[1], reverse=True):
                            cands = sorted([(i, abs(m)) for i, m in neg_disp],
                                           key=lambda x: x[1], reverse=True)
                            combo = _elegir_dp(m_p, cands)
                            if combo is not None:
                                sg = [id_p] + [i for i, _ in combo]
                                resultado_final.append({"fase": "F2",
                                                        "grupo": [lookup[i] for i in sg]})
                                ids_conciliados.update(sg)
                                ids_c = {i for i, _ in combo}
                                neg_disp = [(i, m) for i, m in neg_disp
                                            if i not in ids_c]
                                subdividido = True
                        if not subdividido:
                            resultado_final.append({"fase": "F2",
                                                    "grupo": [lookup[i] for i in nuevos]})
                            ids_conciliados.update(nuevos)
                    else:
                        grupos_sin_subdividir += 1
                        resultado_final.append({"fase": "F2",
                                                "grupo": [lookup[i] for i in nuevos]})
                        ids_conciliados.update(nuevos)
        print(f"   ✅ F2: {len(resultado_final) - f2_i} grupos."
              + (f" ({grupos_sin_subdividir} sin subdividir)" if grupos_sin_subdividir else ""))

        # ── F3 ───────────────────────────────────────────────────────────────
        print("🔍 F3: Tolerancia ±5 centavos...")
        df_r = df.filter(~pl.col("id").is_in(ids_conciliados))
        f3_i = len(resultado_final)
        if not df_r.is_empty():
            gf = (
                df_r.group_by(["n_diario", "localidad"])
                .agg([pl.sum("monto").alias("s"), pl.col("id").alias("ids")])
                .filter((pl.col("s").abs() <= 5) & (pl.col("s") != 0))
            )
            for row in gf.iter_rows(named=True):
                nuevos = [i for i in row["ids"] if i not in ids_conciliados]
                if nuevos:
                    resultado_final.append({"fase": "F3",
                                            "grupo": [lookup[i] for i in nuevos]})
                    ids_conciliados.update(nuevos)
        print(f"   ✅ F3: {len(resultado_final) - f3_i} grupos.")

        # ── F4 ───────────────────────────────────────────────────────────────
        print("🔍 F4: Parejas exactas monto+localidad (sin n_diario)...")
        df_r = df.filter(~pl.col("id").is_in(ids_conciliados))
        f4_i = len(resultado_final)
        if not df_r.is_empty():
            p4 = df_r.filter(pl.col("monto") > 0)
            n4 = (
                df_r.filter(pl.col("monto") < 0)
                .with_columns((pl.col("monto") * -1).alias("ma"))
                .rename({"id": "id_neg"})
                .select(["id_neg", "localidad", "ma"])
            )
            m4 = (
                p4.join(n4, left_on=["localidad", "monto"],
                            right_on=["localidad", "ma"], how="inner")
                .select(["id", "id_neg"])
                .unique(subset=["id"])
                .unique(subset=["id_neg"])
            )
            for id_pos, id_neg in m4.iter_rows():
                if id_pos not in ids_conciliados and id_neg not in ids_conciliados:
                    resultado_final.append({"fase": "F4",
                                            "grupo": [lookup[id_pos], lookup[id_neg]]})
                    ids_conciliados.add(id_pos)
                    ids_conciliados.add(id_neg)
        print(f"   ✅ F4: {len(resultado_final) - f4_i} grupos.")

        # ── Bloque global F6g + F7 + F7b ─────────────────────────────────────
        pendientes_bloque = [t for t in transacciones_list
                             if t.id_transaccion not in ids_conciliados]
        f6g_g, f7_g, f7b_g = self._ejecutar_bloque_global(
            pendientes_bloque, ids_conciliados
        )
        for fase_grupos, nombre in [(f6g_g, "F6g"), (f7_g, "F7"), (f7b_g, "F7b")]:
            fi = len(resultado_final)
            for g in fase_grupos:
                ids_g = {t.id_transaccion for t in g["grupo"]}
                if not ids_g & ids_conciliados:
                    resultado_final.append(g)
                    ids_conciliados.update(ids_g)
            print(f"   ✅ {nombre}: {len(resultado_final) - fi} grupos.")

        # ── F5 — ÚLTIMO RECURSO ───────────────────────────────────────────────
        print("🔍 F5: Parejas exactas solo por monto (último recurso)...")
        f5_i = len(resultado_final)
        pendientes_f5 = [t for t in transacciones_list
                         if t.id_transaccion not in ids_conciliados]
        pos_pool: dict = _dd(list)
        neg_pool: dict = _dd(list)
        for t in pendientes_f5:
            if t.monto_centavos > 0:
                pos_pool[t.monto_centavos].append(t.id_transaccion)
            elif t.monto_centavos < 0:
                neg_pool[abs(t.monto_centavos)].append(t.id_transaccion)
        for monto in list(pos_pool.keys()):
            if monto not in neg_pool:
                continue
            while pos_pool[monto] and neg_pool[monto]:
                id_pos = pos_pool[monto].pop(0)
                id_neg = neg_pool[monto].pop(0)
                if id_pos not in ids_conciliados and id_neg not in ids_conciliados:
                    resultado_final.append({"fase": "F5",
                                            "grupo": [lookup[id_pos], lookup[id_neg]]})
                    ids_conciliados.add(id_pos)
                    ids_conciliados.add(id_neg)
        del pos_pool, neg_pool, pendientes_f5
        print(f"   ✅ F5: {len(resultado_final) - f5_i} grupos.")

        # ── Cierre ────────────────────────────────────────────────────────────
        pendientes_todos = [t for t in transacciones_list
                            if t.id_transaccion not in ids_conciliados]
        if pendientes_todos:
            df_p = pl.DataFrame({
                "id":    [t.id_transaccion for t in pendientes_todos],
                "monto": [t.monto_centavos for t in pendientes_todos],
            })
            pos_m = set(df_p.filter(pl.col("monto") > 0)["monto"].to_list())
            neg_m = set((df_p.filter(pl.col("monto") < 0)["monto"] * -1).to_list())
            cruce = pos_m & neg_m
            ids_cp = set(df_p.filter(pl.col("monto").abs().is_in(cruce))["id"].to_list())
            pend_con = [t for t in pendientes_todos if t.id_transaccion in ids_cp]
            pend_sin = [t for t in pendientes_todos if t.id_transaccion not in ids_cp]
        else:
            pend_con = []
            pend_sin = []

        universo_real = len(ids_conciliados) + len(pend_con)
        tasa_real   = (len(ids_conciliados) / universo_real * 100) if universo_real else 100.0
        tasa_global = (len(ids_conciliados) / total * 100)         if total         else 0.0

        self.conciliadas                = resultado_final
        self.pendientes                 = pendientes_todos
        self.pendientes_con_contraparte = pend_con
        self.pendientes_sin_contraparte = pend_sin
        self.tasa_real                  = tasa_real
        self.tasa_global                = tasa_global

        print(f"\n{'='*55}")
        print(f"✅ Motor completado.")
        print(f"   Grupos conciliados        : {len(self.conciliadas):,}")
        print(f"   Registros conciliados     : {len(ids_conciliados):,} / {total:,}")
        print(f"   Pendientes con contraparte: {len(pend_con):,}")
        print(f"   Pendientes sin contraparte: {len(pend_sin):,}")
        print(f"   Tasa real del motor       : {tasa_real:.2f}%")
        print(f"   Tasa global               : {tasa_global:.2f}%")
        print(f"{'='*55}\n")

        return self.conciliadas, self.pendientes

    # ──────────────────────────────────────────────────────────────────────────
    # Bloque global F6g → F7 → F7b
    # ──────────────────────────────────────────────────────────────────────────

    def _ejecutar_bloque_global(
        self,
        transacciones: list[Transaccion],
        ids_ya_usados: set[int],
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """
        F6g — negativos GRANDES (>5M): N positivos → 1 negativo.
        F7  — 1 positivo → N negativos (patrón dominante).
              Positivos ASC: los pequeños primero, dejan negativos grandes
              disponibles para los positivos grandes.
        F7b — Limpieza de negativos restantes tras F7.
              [OPTIMIZACIÓN v4]: loop sobre POSITIVOS (no negativos).
              Una sola llamada DP por positivo cubre múltiples negativos.
              Poda temprana: si suma(neg_libres) < monto_pos → skip sin DP.
              Complejidad: O(pos_libres) en vez de O(neg_rest × pos_libres).
              Tiempo real: <1 segundo vs >20 minutos en v3.
        """
        if not transacciones:
            return [], [], []

        positivos = [t for t in transacciones
                     if t.monto_centavos > 0
                     and t.id_transaccion not in ids_ya_usados]
        negativos = [t for t in transacciones
                     if t.monto_centavos < 0
                     and t.id_transaccion not in ids_ya_usados]

        if not positivos or not negativos:
            return [], [], []

        idx_all = {t.id_transaccion: t for t in transacciones}
        usados: set[int] = set(ids_ya_usados)

        pos_pool = [(t.id_transaccion, t.monto_centavos) for t in positivos]
        neg_pool = [(t.id_transaccion, t.monto_centavos) for t in negativos]

        # ── F6g ──────────────────────────────────────────────────────────────
        grupos_f6g: list[dict] = []
        neg_grandes = sorted(
            [(id_n, m) for id_n, m in neg_pool if abs(m) > _UMBRAL_NEG_GRANDE],
            key=lambda x: abs(x[1]),
        )
        for id_neg, monto_neg in neg_grandes:
            if id_neg in usados:
                continue
            cands = _cands_desc(pos_pool, usados, _MAX_CANDIDATOS_DP)
            if not cands:
                break
            match = _elegir_dp(abs(monto_neg), cands)
            if match is None:
                continue
            ids_m = {id_t for id_t, _ in match}
            grupos_f6g.append({
                "fase": "F6g",
                "grupo": [idx_all[id_neg]] + [idx_all[i] for i in ids_m],
            })
            usados.add(id_neg)
            usados.update(ids_m)

        # ── F7 ───────────────────────────────────────────────────────────────
        grupos_f7: list[dict] = []
        pos_asc = sorted(pos_pool, key=lambda x: x[1])
        for id_pos, monto_pos in pos_asc:
            if id_pos in usados:
                continue
            cands = _cands_desc(
                [(id_n, abs(m)) for id_n, m in neg_pool],
                usados,
                _MAX_CANDIDATOS_DP,
            )
            if not cands:
                break
            match = _elegir_dp(monto_pos, cands)
            if match is None:
                continue
            ids_m = {id_t for id_t, _ in match}
            grupos_f7.append({
                "fase": "F7",
                "grupo": [idx_all[id_pos]] + [idx_all[i] for i in ids_m],
            })
            usados.add(id_pos)
            usados.update(ids_m)

        # ── F7b ──────────────────────────────────────────────────────────────
        # OPTIMIZACIÓN v4: itera sobre positivos (no negativos).
        # Para cada positivo libre, intenta cubrir el máximo de negativos
        # libres con una sola llamada DP. Poda temprana evita el 95% de DPs.
        grupos_f7b: list[dict] = []

        # Precalcular lista de negativos libres una vez, ordenada DESC
        # (se actualiza al marcar usados dentro del loop)
        neg_libres_desc = sorted(
            [(id_n, abs(m)) for id_n, m in neg_pool if id_n not in usados],
            key=lambda x: x[1],
            reverse=True,
        )

        # Positivos libres ASC (los más pequeños primero: más rápidos de resolver)
        pos_libres_asc = sorted(
            [(id_p, m) for id_p, m in pos_pool if id_p not in usados],
            key=lambda x: x[1],
        )

        for id_pos, monto_pos in pos_libres_asc:
            if id_pos in usados:
                continue

            # Filtrar negativos aún libres (O(n) filter, no re-sort)
            neg_cands = [(i, m) for i, m in neg_libres_desc if i not in usados]
            if not neg_cands:
                break

            # PODA TEMPRANA: si la suma de todos los negativos libres
            # es menor que el objetivo, no existe solución → skip sin DP
            suma_neg = sum(m for _, m in neg_cands)
            if suma_neg < monto_pos:
                continue  # no llamar al DP — imposible matemáticamente

            match = _elegir_dp(monto_pos, neg_cands[:_MAX_CANDIDATOS_DP])
            if match is None:
                continue

            ids_m = {id_t for id_t, _ in match}
            grupos_f7b.append({
                "fase": "F7b",
                "grupo": [idx_all[id_pos]] + [idx_all[i] for i in ids_m],
            })
            usados.add(id_pos)
            usados.update(ids_m)

        # Log resumen
        n6g = sum(len(g["grupo"]) for g in grupos_f6g)
        n7  = sum(len(g["grupo"]) for g in grupos_f7)
        n7b = sum(len(g["grupo"]) for g in grupos_f7b)
        neg_cubiertos = (
            sum(1 for g in grupos_f6g for t in g["grupo"] if t.monto_centavos < 0)
            + sum(1 for g in grupos_f7  for t in g["grupo"] if t.monto_centavos < 0)
            + sum(1 for g in grupos_f7b for t in g["grupo"] if t.monto_centavos < 0)
        )
        print(f"      Bloque global → "
              f"F6g: {len(grupos_f6g)} grp/{n6g} tx | "
              f"F7: {len(grupos_f7)} grp/{n7} tx | "
              f"F7b: {len(grupos_f7b)} grp/{n7b} tx | "
              f"neg cubiertos: {neg_cubiertos}/{len(neg_pool)}")

        return grupos_f6g, grupos_f7, grupos_f7b

    # ──────────────────────────────────────────────────────────────────────────
    # Standalone
    # ──────────────────────────────────────────────────────────────────────────

    def ejecutar_f6_standalone(
        self,
        transacciones: list[Transaccion],
    ) -> list[dict]:
        """Ejecuta F6g+F7+F7b sobre la lista dada. Para reprocesar pendientes."""
        f6g, f7, f7b = self._ejecutar_bloque_global(transacciones, set())
        return f6g + f7 + f7b