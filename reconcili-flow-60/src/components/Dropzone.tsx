import { useCallback, useState, useRef } from "react";
import { Upload, FileSpreadsheet, X } from "lucide-react";
import { cn } from "@/lib/utils";

interface DropzoneProps {
  file: File | null;
  onFileSelect: (file: File) => void;
  onClear: () => void;
}

export default function Dropzone({ file, onFileSelect, onClear }: DropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const f = e.dataTransfer.files[0];
    if (f && (f.name.endsWith(".xlsx") || f.name.endsWith(".xls") || f.name.endsWith(".csv"))) {
      onFileSelect(f);
    }
  }, [onFileSelect]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) onFileSelect(f);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  };

  if (file) {
    return (
      <div className="border-2 border-primary/30 rounded-2xl p-6 bg-primary/5 flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl gradient-primary flex items-center justify-center flex-shrink-0">
          <FileSpreadsheet className="w-6 h-6 text-primary-foreground" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-card-foreground truncate">{file.name}</p>
          <p className="text-sm text-muted-foreground">{formatSize(file.size)}</p>
        </div>
        <button onClick={onClear} className="p-2 rounded-full hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors">
          <X className="w-5 h-5" />
        </button>
      </div>
    );
  }

  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={cn(
        "border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-300",
        isDragging
          ? "border-primary bg-primary/5 scale-[1.02]"
          : "border-border bg-muted/50 hover:border-primary hover:bg-primary/5"
      )}
    >
      <Upload className="w-10 h-10 text-primary mx-auto mb-3" />
      <p className="text-muted-foreground text-sm">
        <span className="font-semibold text-card-foreground">Haz clic para subir</span> o arrastra tu archivo Excel
      </p>
      <p className="text-xs text-muted-foreground mt-2">Formatos: .xlsx, .xls, .csv (máx 20.000 registros)</p>
      <input
        ref={inputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        onChange={handleChange}
        className="hidden"
      />
    </div>
  );
}
