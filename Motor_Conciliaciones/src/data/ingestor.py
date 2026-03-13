import polars as pl

TIPOS_VALIDOS = {"SIF82", "TES82"}


class DataIngestor:
    def __init__(self, ruta_archivo: str):
        self.ruta_archivo = ruta_archivo

    def _leer_hoja_correcta(self) -> "pl.DataFrame":
        """
        Prueba hojas comunes por nombre y por índice (0, 1, 2...)
        hasta encontrar una que tenga la columna 'Cuenta'.
        Sin dependencias externas — solo polars.
        """
        # Nombres comunes a intentar primero
        nombres_comunes = [
            "Hoja1", "Hoja 1", "Sheet1", "Sheet 1", "Data", "Datos", "data"
        ]

        candidatos = nombres_comunes + list(range(10))  # índices 0-9 como fallback

        for candidato in candidatos:
            try:
                kwargs = {"sheet_name": candidato} if isinstance(candidato, str)                          else {"sheet_id": candidato + 1}  # polars usa 1-based
                df_test = pl.read_excel(
                    self.ruta_archivo, engine="calamine", **kwargs
                )
                cols = [c.strip() for c in df_test.columns]
                if "Cuenta" in cols:
                    print(f"✅ Hoja seleccionada: '{candidato}'")
                    df_test.columns = cols
                    return df_test
            except Exception:
                continue

        raise ValueError(
            "No se encontró ninguna hoja con columna 'Cuenta'. "
            "Verifica que estás subiendo el archivo de datos, no un reporte."
        )

    def procesar_excel(self) -> pl.DataFrame:
        df = self._leer_hoja_correcta()

        df.columns = [c.strip() for c in df.columns]
        print(f"📋 Columnas detectadas: {df.columns}")
        print(f"📊 Total filas brutas: {len(df):,}")

        col_ndiario   = next((c for c in ["N.º diario","N.º Diario","Nº diario","N° diario","Diario"] if c in df.columns), None)
        col_localidad = next((c for c in ["Localidad","localidad","LOCALIDAD"] if c in df.columns), None)
        col_tipo      = next((c for c in ["Tipo","tipo","TIPO"] if c in df.columns), None)
        col_periodo   = next((c for c in ["Período","Periodo","período","periodo","PERIODO"] if c in df.columns), None)

        for nombre, val in [("N.º diario", col_ndiario), ("Localidad", col_localidad),
                            ("Tipo", col_tipo), ("Período", col_periodo)]:
            if val is None:
                raise ValueError(f"No se encontró '{nombre}'. Columnas: {df.columns}")
            print(f"✅ {nombre} → '{val}'")

        df_sel = df.select([
            pl.col("Descripción").alias("descripcion"),
            pl.col("Cuenta").cast(pl.Utf8).alias("cuenta_contable"),
            (pl.col("Importe").fill_null(0) * 100).round(0).cast(pl.Int64).alias("monto_centavos"),
            pl.col(col_ndiario).alias("n_diario_raw"),
            pl.col(col_localidad).cast(pl.Utf8).alias("localidad"),
            pl.col(col_tipo).cast(pl.Utf8).alias("tipo"),
            pl.col(col_periodo).cast(pl.Utf8).alias("periodo"),
        ])

        # Filtro 1: eliminar fila de totales (n_diario nulo)
        df_sel = df_sel.filter(pl.col("n_diario_raw").is_not_null())

        # Filtro 2: solo SIF82 y TES82
        antes = len(df_sel)
        df_sel = df_sel.filter(pl.col("tipo").is_in(list(TIPOS_VALIDOS)))
        print(f"\n🔍 Filtro tipo ({', '.join(sorted(TIPOS_VALIDOS))}): "
              f"{antes:,} → {len(df_sel):,} (descartados: {antes-len(df_sel):,})")

        periodos = sorted(df_sel["periodo"].drop_nulls().unique().to_list())
        print(f"📅 Períodos detectados: {periodos}")

        df_limpio = (
            df_sel
            .with_columns(pl.col("n_diario_raw").cast(pl.Int64).alias("n_diario"))
            .drop("n_diario_raw")
            # ← tipo SE CONSERVA, lo necesita la DB y el reporter
        )

        print(f"📦 Registros válidos para conciliar: {len(df_limpio):,}")
        return df_limpio