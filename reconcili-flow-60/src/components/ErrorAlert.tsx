import { AlertCircle, X } from "lucide-react";

interface ErrorAlertProps {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorAlert({ message, onDismiss }: ErrorAlertProps) {
  return (
    <div className="bg-destructive/10 border border-destructive/30 rounded-2xl p-5 flex items-start gap-4">
      <div className="w-10 h-10 rounded-xl bg-destructive/20 flex items-center justify-center flex-shrink-0">
        <AlertCircle className="w-5 h-5 text-destructive" />
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-semibold text-destructive mb-1">Error en la Conciliación</h4>
        <p className="text-sm text-destructive/80">{message}</p>
      </div>
      {onDismiss && (
        <button onClick={onDismiss} className="p-1 rounded-full hover:bg-destructive/10 text-destructive transition-colors flex-shrink-0">
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}
