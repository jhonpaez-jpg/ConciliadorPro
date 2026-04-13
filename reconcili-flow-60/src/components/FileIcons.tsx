// Iconos SVG inline para Excel y PDF
export function ExcelIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" opacity=".2"/>
      <path d="M14 2v6h6"/>
      <path d="M8 13l2.5 4 2.5-4M8 17l2.5-4 2.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
    </svg>
  );
}

export function PdfIcon({ className = "w-4 h-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6z" opacity=".2"/>
      <path d="M14 2v6h6"/>
      <text x="5" y="19" fontSize="7" fontWeight="bold" fill="currentColor" fontFamily="sans-serif">PDF</text>
    </svg>
  );
}
