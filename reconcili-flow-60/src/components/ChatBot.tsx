import { useState, useRef, useEffect } from "react";
import { MessageCircle, X, Send, Bot, User, Minimize2 } from "lucide-react";
import { useReconciliation } from "@/context/ReconciliationContext";

interface Message {
  id: number;
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "¿Cuál es la tasa de conciliación?",
  "¿Qué significa F1, F2, F3?",
  "¿Por qué hay registros pendientes?",
  "¿Cómo descargo el reporte?",
];

function getResponse(msg: string, ctx: string): string {
  const q = msg.toLowerCase();
  if (q.includes("tasa") || q.includes("efectividad") || q.includes("%"))
    return `La tasa de conciliación mide el porcentaje de registros emparejados exitosamente. ${ctx} Una tasa sobre 60% es muy buena para volúmenes de 300k+ registros.`;
  if (q.includes("f1") || q.includes("fast"))
    return "F1 (Fast-Pass) busca coincidencias exactas 1:1 por n_diario + localidad + monto. Es la fase más rápida y precisa.";
  if (q.includes("f2") || q.includes("subset"))
    return "F2 (Subset Sum) usa programación dinámica para encontrar grupos N:N que sumen cero. Puede encontrar combinaciones de 2 a 10 transacciones que se cancelen entre sí.";
  if (q.includes("f3") || q.includes("toleran"))
    return "F3 aplica una tolerancia de ±5 centavos para absorber diferencias de redondeo entre sistemas.";
  if (q.includes("f4"))
    return "F4 empareja por monto + localidad sin considerar el n_diario, útil cuando los diarios no coinciden por errores de captura.";
  if (q.includes("f5") || q.includes("monto puro") || q.includes("global"))
    return "F5 es la fase más agresiva: empareja solo por monto exacto a nivel global, sin localidad ni n_diario.";
  if (q.includes("pendiente"))
    return `Los registros pendientes no encontraron contraparte con ninguna fase. ${ctx} Pueden deberse a: transacciones en otro sistema, errores de captura, o períodos distintos.`;
  if (q.includes("descarg") || q.includes("excel") || q.includes("reporte"))
    return "El reporte Excel se genera automáticamente al terminar. Tiene 3 hojas: RESUMEN, LOGRADO y PENDIENTES. Puedes descargarlo con el botón azul.";
  if (q.includes("cuánto") || q.includes("tiempo") || q.includes("tarda"))
    return "El procesamiento de ~350k registros toma entre 5-15 minutos. Puedes ver el progreso en tiempo real en la sección Ejecutar.";
  if (q.includes("hola") || q.includes("buenos") || q.includes("buenas"))
    return `¡Hola! Soy el asistente del Conciliador Pro. ${ctx} ¿En qué te puedo ayudar hoy?`;
  return `Entiendo tu pregunta sobre "${msg}". ${ctx} Para más detalles técnicos, revisa la documentación del motor.`;
}

export default function ChatBot() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      id: 0,
      role: "assistant",
      content: "¡Hola! Soy el asistente del Conciliador Pro. Puedo ayudarte a interpretar resultados, entender las fases del motor y resolver dudas. ¿En qué te puedo ayudar?",
    },
  ]);
  const endRef = useRef<HTMLDivElement>(null);
  const { result } = useReconciliation();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ctx = result
    ? `Datos actuales: Cuenta ${result.cuenta_procesada}, ${(result.conciliados ?? 0).toLocaleString()} conciliados de ${(result.total_leido ?? 0).toLocaleString()} (${(result.tasa_conciliacion ?? 0).toFixed(1)}% efectividad), ${(result.pendientes ?? 0).toLocaleString()} pendientes.`
    : "Aún no hay datos de conciliación cargados.";

  const send = async (text?: string) => {
    const content = (text || input).trim();
    if (!content || loading) return;
    setInput("");

    const userMsg: Message = { id: Date.now(), role: "user", content };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    await new Promise((r) => setTimeout(r, 600 + Math.random() * 400));

    const respuesta = getResponse(content, ctx);
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
    <div className="fixed bottom-6 right-6 w-96 h-[500px] bg-card rounded-2xl shadow-2xl flex flex-col overflow-hidden z-50 border border-border">
      {/* Header */}
      <div className="gradient-primary px-4 py-3 flex justify-between items-center flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-primary-foreground/20 rounded-full flex items-center justify-center">
            <Bot className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <p className="text-sm font-semibold text-primary-foreground">Asistente Conciliador</p>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 rounded-full bg-success" />
              <span className="text-[11px] text-primary-foreground/70">En línea</span>
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
              {msg.role === "assistant" ? <Bot className="w-3.5 h-3.5 text-primary" /> : <User className="w-3.5 h-3.5 text-muted-foreground" />}
            </div>
            <div className={`max-w-[75%] px-3 py-2 rounded-xl text-sm ${msg.role === "assistant" ? "bg-muted text-card-foreground" : "gradient-primary text-primary-foreground"}`}>
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

      {/* Suggestions */}
      {messages.length <= 1 && (
        <div className="px-4 pb-2 flex flex-wrap gap-1.5">
          {SUGGESTIONS.map((s) => (
            <button key={s} onClick={() => send(s)} className="text-xs bg-primary/10 text-primary px-2.5 py-1 rounded-full hover:bg-primary/20 transition-colors">
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
          placeholder="Escribe tu pregunta..."
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
