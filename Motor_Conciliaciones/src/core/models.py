from dataclasses import dataclass


@dataclass
class LoteEjecucion:
    id_lote:      int
    fecha_inicio: str
    estado:       str


@dataclass(frozen=True)
class Transaccion:
    id_transaccion:  int
    descripcion:     str
    cuenta_contable: str
    monto_centavos:  int
    id_lote:         int
    localidad:       str = ""
    n_diario:        int = 0
    periodo:         str = ""
    tipo:            str = ""          # ← "SIF82" o "TES82"
    estado_tx:       str = "PENDIENTE"
    id_conciliacion: int | None = None


@dataclass
class Conciliacion:
    id_conciliacion:     int
    fecha_conciliacion:  str
    estado_conciliacion: str