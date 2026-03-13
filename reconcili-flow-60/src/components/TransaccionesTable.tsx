import { useState, useEffect } from "react";
import { X, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import axios from "axios";

interface TransaccionItem {
  id: string;
  tipo: string;
  periodo: string;
  descripcion: string;
  localidad: string;
  monto: number;
  n_diario: string;
  grupo?: number;
  fase?: string;
}

interface Props {
  estado: "CONCILIADO" | "PENDIENTE";
  cuenta: string;
  onClose: () => void;
}

const FASE_COLORS: Record<string, string> = {
  F1: "bg-success/10 text-success",
  F2: "bg-primary/10 text-primary",
  F3: "bg-warning/10 text-warning",
  F4: "bg-accent-foreground/10 text-accent-foreground",
  F5: "bg-info/10 text-info",
};

export default function TransaccionesTable({ estado, cuenta, onClose }: Props) {
  const [items, setItems] = useState<TransaccionItem[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios
      .get("/api/transacciones/", {
        params: { estado, cuenta, page, limit: 100 },
      })
      .then(({ data }) => {
        setItems(data.items ?? []);
        setTotalPages(data.pages ?? 1);
        setTotal(data.total ?? 0);
      })
      .catch(() => {
        setItems([]);
        setTotal(0);
      })
      .finally(() => setLoading(false));
  }, [estado, cuenta, page]);

  const isConciliado = estado === "CONCILIADO";
  const headerColor = isConciliado ? "text-success" : "text-warning";

  return (
    <div className="bg-card rounded-2xl shadow-card overflow-hidden">
      {/* Header */}
      <div className="flex justify-between items-center p-5 border-b border-border">
        <div>
          <h3 className={`text-base font-semibold ${headerColor}`}>
            {isConciliado ? "✅ Registros Conciliados" : "⏳ Registros Pendientes"}
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            {total.toLocaleString()} registros — Cuenta {cuenta}
          </p>
        </div>
        <button onClick={onClose} className="p-2 rounded-full hover:bg-muted transition-colors text-muted-foreground hover:text-card-foreground">
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      ) : items.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground text-sm">No se encontraron registros.</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                {["Tipo", "Período", "Descripción", "Localidad", "Monto (COP)", "N.º Diario", ...(isConciliado ? ["Grupo", "Fase"] : [])].map(
                  (col) => (
                    <th key={col} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase">
                      {col}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={i} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-primary/10 text-primary">{item.tipo}</span>
                  </td>
                  <td className="px-4 py-3 text-card-foreground">{item.periodo}</td>
                  <td className="px-4 py-3 text-card-foreground max-w-[200px] truncate">{item.descripcion}</td>
                  <td className="px-4 py-3 text-card-foreground">{item.localidad}</td>
                  <td className={`px-4 py-3 font-medium ${(item.monto ?? 0) >= 0 ? "text-success" : "text-destructive"}`}>
                    {(item.monto ?? 0) >= 0 ? "+" : ""}
                    {(item.monto ?? 0).toLocaleString("es-CO", { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-card-foreground">{item.n_diario}</td>
                  {isConciliado && (
                    <td className="px-4 py-3">
                      <span className="px-2 py-0.5 rounded text-xs font-medium bg-success/10 text-success">
                        G-{item.grupo ?? "—"}
                      </span>
                    </td>
                  )}
                  {isConciliado && (
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${FASE_COLORS[item.fase ?? ""] ?? "bg-muted text-muted-foreground"}`}>
                        {item.fase ?? "—"}
                      </span>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-between items-center px-5 py-3 border-t border-border">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="px-4 py-2 rounded-lg border border-border text-sm disabled:opacity-40 hover:border-primary transition-colors flex items-center gap-1 text-card-foreground"
          >
            <ChevronLeft className="w-4 h-4" /> Anterior
          </button>
          <span className="text-xs text-muted-foreground">
            Página {page} de {totalPages} ({total.toLocaleString()} registros)
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="px-4 py-2 rounded-lg border border-border text-sm disabled:opacity-40 hover:border-primary transition-colors flex items-center gap-1 text-card-foreground"
          >
            Siguiente <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
