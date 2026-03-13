import { Bot } from "lucide-react";

export default function FAB() {
  return (
    <button
      onClick={() => alert("Asistente de Conciliación: ¿En qué puedo ayudarte?\n\n• Ejecutar conciliación automático\n• Revisar anomalías\n• Generar reporte mensual")}
      className="fixed bottom-8 right-8 w-[60px] h-[60px] rounded-full gradient-primary text-primary-foreground flex items-center justify-center shadow-lg animate-pulse-glow hover:scale-110 hover:rotate-90 transition-all duration-300 z-50"
    >
      <Bot className="w-6 h-6" />
    </button>
  );
}
