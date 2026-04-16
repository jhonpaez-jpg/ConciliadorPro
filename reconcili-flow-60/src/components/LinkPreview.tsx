import { useState, useEffect, useCallback } from "react";

export default function LinkPreview() {
  const [preview, setPreview] = useState<string | null>(null);

  const handleMouseOver = useCallback((e: MouseEvent) => {
    const target = (e.target as HTMLElement).closest("[data-href]");
    if (target) {
      const href = target.getAttribute("data-href");
      if (href) setPreview(href);
    }
  }, []);

  const handleMouseOut = useCallback((e: MouseEvent) => {
    const target = (e.target as HTMLElement).closest("[data-href]");
    if (target) setPreview(null);
  }, []);

  useEffect(() => {
    document.addEventListener("mouseover", handleMouseOver);
    document.addEventListener("mouseout", handleMouseOut);
    return () => {
      document.removeEventListener("mouseover", handleMouseOver);
      document.removeEventListener("mouseout", handleMouseOut);
    };
  }, [handleMouseOver, handleMouseOut]);

  if (!preview) return null;

  return (
    <div className="fixed bottom-4 left-4 z-[9999] flex items-center gap-2 bg-card/95 backdrop-blur-sm border border-border rounded-lg px-3 py-1.5 shadow-lg text-xs text-muted-foreground font-mono max-w-[420px] truncate pointer-events-none">
      <span className="text-primary font-semibold shrink-0">Conciliador</span>
      <span className="truncate">{preview}</span>
    </div>
  );
}
