import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Bot, User, Minimize2 } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";
import { useApp, getMonthName } from "@/context/AppContext";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "¿Qué hace cada fase del motor?",
  "¿Por qué hay registros pendientes?",
  "¿Cómo descargo el reporte PDF?",
  "¿Qué es la tasa de conciliación?",
  "¿Cómo cancelo una conciliación?",
];

// ── Palabras clave que indican que la pregunta es sobre la app ────────────────
const KEYWORDS_APP = [
  "concilia", "fase", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f7b",
  "fast", "subset", "toleran", "localidad", "monto", "pendiente", "logrado",
  "reporte", "excel", "pdf", "descarg", "tasa", "efectividad", "registr",
  "motor", "dashboard", "historial", "ejecutar", "cancelar", "lote",
  "cuenta", "período", "periodo", "conciliado", "transaccion", "transacción",
  "sif82", "tes82", "n_diario", "programación", "programacion", "dinamica",
  "dp", "algoritmo", "hola", "buenos", "buenas", "gracias", "ayuda",
  "qué es", "que es", "cómo", "como", "cuánto", "cuanto", "cuál", "cual",
  "explica", "dime", "muestra", "ver", "navegar", "sección", "seccion",
  "app", "aplicacion", "aplicación", "pagina", "página", "botón", "boton",
];

function isOnTopic(msg: string): boolean {
  const q = msg.toLowerCase();
  return KEYWORDS_APP.some((kw) => q.includes(kw));
}

// ── Motor de respuestas ───────────────────────────────────────────────────────
function getResponse(msg: string, ctx: string, mesLabel: string): string {
  const q = msg.toLowerCase();

  // Fuera de tema
  if (!isOnTopic(q)) {
    return "Lo siento, solo puedo responder preguntas relacionadas con el Conciliador Pro: fases del motor, resultados, reportes, navegación y configuración de la aplicación. Para otras consultas, no tengo la capacidad de ayudarte.";
  }

  // Saludos
  if (q.match(/^(hola|buenos|buenas|hey|hi)\b/)) {
    return `¡Hola! Soy el asistente del Conciliador Pro. Puedo ayudarte con las fases del motor, interpretar resultados, descargar reportes y navegar la aplicación. ${ctx} ¿En qué te puedo ayudar?`;
  }

  // Tasa / efectividad
  if (q.includes("tasa") || q.includes("efectividad") || (q.includes("%") && q.includes("concilia"))) {
    return `La tasa de conciliación es el porcentaje de registros emparejados exitosamente sobre el total. ${ctx} Una tasa superior al 85% es excelente para volúmenes grandes. El motor v4 alcanza ~99% en condiciones óptimas.`;
  }

  // F1
  if (q.includes("f1") || q.includes("fast-pass") || q.includes("fast pass")) {
    return "F1 — Fast-Pass: busca coincidencias exactas 1:1 usando n_diario + localidad + monto simultáneamente. Es la fase más rápida y precisa. Suele conciliar entre el 40-60% del total en segundos.";
  }

  // F2
  if (q.includes("f2") || (q.includes("subset") && !q.includes("global"))) {
    return "F2 — Subset Sum: usa programación dinámica para encontrar grupos N:N (varios positivos y negativos) que sumen exactamente cero, dentro del mismo n_diario y localidad. Puede encontrar combinaciones de hasta 20 transacciones.";
  }

  // F3
  if (q.includes("f3") || q.includes("toleran") || q.includes("centavo")) {
    return "F3 — Tolerancia: igual que F2 pero acepta grupos cuya suma difiere en máximo ±5 centavos. Absorbe diferencias de redondeo entre sistemas contables.";
  }

  // F4
  if (q.includes("f4") || (q.includes("localidad") && !q.includes("f6"))) {
    return "F4 — Monto + Localidad: empareja parejas exactas 1:1 por monto y localidad, sin considerar el n_diario. Útil cuando los números de diario no coinciden por errores de captura.";
  }

  // F5
  if (q.includes("f5") || q.includes("monto puro") || (q.includes("monto") && q.includes("global"))) {
    return "F5 — Monto Puro Global: último recurso 1:1. Empareja solo por monto exacto a nivel global, sin localidad ni n_diario. Se ejecuta al final para capturar lo que las fases anteriores no encontraron.";
  }

  // F6
  if (q.includes("f6") || (q.includes("subset") && q.includes("global")) || q.includes("n positivos") || q.includes("neg. grandes")) {
    return "F6 — Subset Sum Global: N positivos → 1 negativo. Ataca negativos grandes (>500K) usando programación dinámica sobre el pool global de pendientes. Se ejecuta antes de F5 para aprovechar patrones complejos.";
  }

  // F7
  if (q.includes("f7b") || q.includes("limpieza final") || q.includes("final cleaning")) {
    return "F7b — Final Cleaning B: limpieza de positivos restantes tras F7. Itera sobre positivos libres e intenta cubrir N negativos con una sola llamada DP. Optimizado en v4: de >20 minutos a <1 segundo.";
  }
  if (q.includes("f7") || q.includes("1 positivo") || q.includes("final clean")) {
    return "F7 — Final Cleaning: 1 positivo → N negativos. Itera positivos de menor a mayor (ASC) para dejar los negativos grandes disponibles para positivos grandes. Junto con F7b forma el bloque de limpieza final.";
  }

  // Todas las fases
  if (q.includes("todas") && (q.includes("fase") || q.includes("motor"))) {
    return "El motor tiene 8 fases en orden:\n• F1: Fast-Pass 1:1 exacto\n• F2: Subset Sum N:N suma cero\n• F3: Tolerancia ±5 centavos\n• F4: Monto + Localidad\n• F6: Subset Sum Global (N pos → 1 neg)\n• F7: Final Cleaning (1 pos → N neg)\n• F7b: Limpieza final positivos\n• F5: Monto Puro (último recurso)\n\nF1-F4 se ejecutan por localidad. F6/F7/F7b sobre el pool global. F5 al final.";
  }

  // Pendientes
  if (q.includes("pendiente")) {
    return `Los registros pendientes no encontraron contraparte en ninguna de las 8 fases. ${ctx} Causas comunes: transacciones en otro período, errores de captura, montos únicos sin par, o transacciones que pertenecen a otro sistema.`;
  }

  // Reportes / descarga
  if (q.includes("pdf")) {
    return "Para descargar el PDF: ve a la sección Reportes en el menú lateral. Cada reporte tiene su botón PDF rojo. El PDF incluye KPIs, desglose por fase, muestra de conciliados y pendientes, generado desde la base de datos.";
  }
  if (q.includes("excel") || q.includes("descarg") || q.includes("reporte")) {
    return "Los reportes Excel están en la sección Reportes. Hay 4 tipos: Conciliación Completa (F1-F7b), Métricas por Fase, Pendientes y Anomalías, y Evolución del Motor. También puedes descargar desde el Historial.";
  }

  // Cancelar
  if (q.includes("cancel")) {
    return "Para cancelar una conciliación en curso: en la sección Ejecutar, mientras el proceso está corriendo aparece el botón rojo 'Cancelar conciliación'. Al presionarlo se envía la señal de parada al servidor y el proceso se detiene limpiamente.";
  }

  // Historial
  if (q.includes("historial")) {
    return `El Historial muestra todas las conciliaciones realizadas, guardadas permanentemente en la base de datos. Puedes filtrar por mes con las flechas del header o ver todo el historial. Datos de ${mesLabel}: ${ctx}`;
  }

  // Dashboard
  if (q.includes("dashboard") || q.includes("inicio")) {
    return "El Dashboard muestra el resumen del mes seleccionado: total de registros, conciliados, pendientes y efectividad. Usa las flechas ← → del header para navegar entre meses. Los datos vienen directamente de la base de datos.";
  }

  // Tiempo / duración
  if (q.includes("tiempo") || q.includes("tarda") || q.includes("demora") || q.includes("cuánto")) {
    return "El tiempo depende del volumen. Para ~30,000 registros: F1-F4 toman 1-3 min, F6/F7 entre 2-10 min según complejidad. El motor v4 optimizó F7b de >20 minutos a <1 segundo. Puedes ver el progreso en tiempo real.";
  }

  // Navegación
  if (q.includes("navegar") || q.includes("sección") || q.includes("seccion") || q.includes("menú") || q.includes("menu")) {
    return "La aplicación tiene estas secciones en el menú lateral:\n• Dashboard: resumen del mes\n• Ejecutar: subir archivo y procesar\n• Historial: todas las ejecuciones\n• F1-F7b: detalle de cada fase\n• Reportes: descargar Excel y PDF\n• Ajustes: configuración del motor";
  }

  // SIF82 / TES82
  if (q.includes("sif") || q.includes("tes") || q.includes("tipo")) {
    return "SIF82 y TES82 son los dos tipos de documentos que procesa el motor. El ingestor filtra y normaliza ambos tipos desde el Excel de entrada. En los reportes puedes ver el desglose por tipo.";
  }

  // Gracias
  if (q.includes("gracias") || q.includes("thank")) {
    return "¡Con gusto! Si tienes más preguntas sobre el Conciliador Pro, aquí estaré. 😊";
  }

  // Fallback dentro de tema
  return `Entiendo tu pregunta. ${ctx} Para más detalles sobre "${msg}", te recomiendo revisar la sección correspondiente en el menú lateral o consultar los reportes generados. ¿Puedo ayudarte con algo más específico?`;
}

// ── Componente ────────────────────────────────────────────────────────────────
export default function ChatBot() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "assistant",
      content: "¡Hola! Soy el asistente del Conciliador Pro. Puedo ayudarte a entender las fases del motor (F1–F7b), interpretar resultados, navegar la aplicación y descargar reportes. ¿En qué te puedo ayudar?",
    },
  ]);
  const endRef = useRef<HTMLDivElement>(null);
  const { result, history, getHistoryByMonth } = useReconciliation();
  const { currentMonthIndex, currentYear } = useApp();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const mesLabel = `${getMonthName(currentMonthIndex)} ${currentYear}`;
  const historialMes = getHistoryByMonth(currentMonthIndex, currentYear);
  const dataMes: any = historialMes[0] ?? result ?? history[0] ?? null;

  const ctx = dataMes
    ? `Datos de ${mesLabel}: Cuenta ${dataMes.cuenta_procesada ?? dataMes.cuenta ?? "—"}, ${(dataMes.conciliados ?? 0).toLocaleString()} conciliados de ${(dataMes.total_leido ?? dataMes.total ?? 0).toLocaleString()} (${((dataMes.tasa_conciliacion ?? dataMes.tasa) ?? 0).toFixed(1)}% efectividad), ${(dataMes.pendientes ?? 0).toLocaleString()} pendientes.`
    : "Aún no hay datos de conciliación para este mes.";

  const send = async (text?: string) => {
    const content = (text || input).trim();
    if (!content || loading) return;
    setInput("");

    const userMsg: Message = { id: Date.now(), role: "user", content };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    await new Promise((r) => setTimeout(r, 400 + Math.random() * 300));

    const respuesta = getResponse(content, ctx, mesLabel);
    setMessages((prev) => [...prev, { id: Date.now() + 1, role: "assistant", content: respuesta }]);
    setLoading(false);
  };

  if (!open)
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 gradient-primary rounded-full shadow-2xl flex items-center justify-center hover:scale-110 hover:-translate-y-1 transition-all z-50"
        title="Abrir asistente"
      >
        <MessageCircle className="w-6 h-6 text-primary-foreground" />
      </button>
    );

  return (
    <div className="fixed bottom-6 right-6 w-96 h-[520px] bg-card rounded-2xl shadow-2xl flex flex-col overflow-hidden z-50 border border-border">
      {/* Header */}
      <div className="gradient-primary px-4 py-3 flex justify-between items-center flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-foreground/20 rounded-full flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <p className="text-sm font-semibold text-primary-foreground">Asistente Conciliador Pro</p>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-success" />
              <span className="text-[11px] text-primary-foreground/70">Motor v4 — F1 a F7b</span>
            </div>
          </div>
        </div>
        <div className="flex gap-1">
          <button onClick={() => setOpen(false)} className="p-1.5 text-primary-foreground/70 hover:text-primary-foreground hover:bg-primary-foreground/20 rounded-lg transition-colors">
            <Minimize2 className="w-4 h-4" />
          </button>
          <button onClick={() => setOpen(false)} className="p-1.5 text-primary-foreground/70 hover:text-primary-foreground hover:bg-primary-foreground/20 rounded-lg transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === "assistant" ? "bg-primary/10" : "bg-muted"}`}>
              {msg.role === "assistant"
                ? <Bot className="w-3.5 h-3.5 text-primary" />
                : <User className="w-3.5 h-3.5 text-muted-foreground" />}
            </div>
            <div className={`max-w-[78%] px-3 py-2 rounded-xl text-sm whitespace-pre-line leading-relaxed ${
              msg.role === "assistant"
                ? "bg-muted text-card-foreground"
                : "gradient-primary text-primary-foreground"
            }`}>
              {msg.content}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-2">
            <div className="w-7 h-7 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
              <Bot className="w-3.5 h-3.5 text-primary" />
            </div>
            <div className="bg-muted px-4 py-3 rounded-xl flex gap-1">
              {[0, 150, 300].map((delay) => (
                <div key={delay} className="w-2 h-2 bg-muted-foreground/40 rounded-full animate-bounce" style={{ animationDelay: `${delay}ms` }} />
              ))}
            </div>
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Sugerencias */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-xs bg-primary/10 text-primary px-2.5 py-1 rounded-full hover:bg-primary/20 transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="px-4 py-3 border-t border-border flex gap-2 flex-shrink-0">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          placeholder="Pregunta sobre el Conciliador Pro..."
          disabled={loading}
          className="flex-1 bg-muted rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-60"
        />
        <button
          onClick={() => send()}
          disabled={!input.trim() || loading}
          className="w-9 h-9 gradient-primary rounded-xl flex items-center justify-center disabled:opacity-50 hover:scale-105 transition-all flex-shrink-0"
        >
          <Send className="w-4 h-4 text-primary-foreground" />
        </button>
      </div>
    </div>
  );
}
