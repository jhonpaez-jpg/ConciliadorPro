import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Cell, ResponsiveContainer } from "recharts";

interface ChartSectionProps {
  conciliados: number;
  pendientes: number;
  tasa?: number;
}

export default function ChartSection({ conciliados = 0, pendientes = 0, tasa }: ChartSectionProps) {
  const safeConciliados = conciliados ?? 0;
  const safePendientes = pendientes ?? 0;
  const total = safeConciliados + safePendientes;
  const tasaReal = tasa ?? (total > 0 ? (safeConciliados / total) * 100 : 0);

  const barData = [
    { name: "Total", valor: total, fill: "hsl(var(--primary))", pct: "100%" },
    { name: "Conciliados", valor: safeConciliados, fill: "hsl(var(--success))", pct: tasaReal.toFixed(1) + "%" },
    { name: "Pendientes", valor: safePendientes, fill: "hsl(var(--warning))", pct: (100 - tasaReal).toFixed(1) + "%" },
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="bg-card border border-border rounded-xl p-3 shadow-lg text-sm">
        <p className="font-semibold text-card-foreground">{d.name}</p>
        <p className="text-muted-foreground">{(d.valor ?? 0).toLocaleString()} registros</p>
        <p className="text-muted-foreground">{d.pct} del total</p>
      </div>
    );
  };

  const badgeColor = tasaReal >= 80
    ? "bg-success/10 text-success"
    : tasaReal >= 50
    ? "bg-warning/10 text-warning"
    : "bg-destructive/10 text-destructive";

  return (
    <div className="bg-card rounded-2xl p-6 shadow-card">
      <div className="flex justify-between items-center mb-6">
        <h3 className="text-base font-semibold text-card-foreground">📊 Análisis de Conciliación</h3>
        <span className={`px-3 py-1 rounded-full text-xs font-medium ${badgeColor}`}>
          {tasaReal.toFixed(1)}% efectividad
        </span>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={barData} barSize={48}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="name" tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
            <YAxis
              tickFormatter={(v: number) => (v >= 1000 ? (v / 1000).toFixed(0) + "k" : String(v))}
              tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="valor" radius={[8, 8, 0, 0]}>
              {barData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-4 gap-4 mt-6">
        {[
          { label: "Total procesado", value: total.toLocaleString(), color: "text-primary" },
          { label: "Conciliados", value: safeConciliados.toLocaleString(), color: "text-success" },
          { label: "Pendientes", value: safePendientes.toLocaleString(), color: "text-warning" },
          { label: "Tasa real", value: tasaReal.toFixed(2) + "%", color: tasaReal >= 80 ? "text-success" : "text-warning" },
        ].map(({ label, value, color }) => (
          <div key={label} className="text-center p-3 bg-muted/50 rounded-xl">
            <p className={`text-lg font-bold ${color}`}>{value}</p>
            <p className="text-xs text-muted-foreground">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
