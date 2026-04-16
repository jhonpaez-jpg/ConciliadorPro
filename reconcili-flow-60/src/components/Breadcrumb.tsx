import { ChevronRight, Home } from "lucide-react";
import { useApp, SectionId } from "@/context/AppContext";

const SECTION_PATHS: Record<
  SectionId,
  { label: string; parent?: SectionId; slug: string }
> = {
  dashboard: { label: "Dashboard", slug: "/dashboard" },
  ejecutar: {
    label: "Ejecutar Conciliación",
    slug: "/ejecutar-conciliacion",
    parent: "dashboard",
  },
  programadas: {
    label: "Conciliaciones Programadas",
    slug: "/programadas",
    parent: "dashboard",
  },
  historial: { label: "Historial", slug: "/historial", parent: "dashboard" },
  fastpass: {
    label: "Fast-Pass (F1)",
    slug: "/fases/fast-pass-f1",
    parent: "dashboard",
  },
  subsetsum: {
    label: "Subset Sum (F2)",
    slug: "/fases/subset-sum-f2",
    parent: "dashboard",
  },
  tolerancia: {
    label: "Tolerancia F3",
    slug: "/fases/tolerancia-f3",
    parent: "dashboard",
  },
  localidad: {
    label: "Localidad F4",
    slug: "/fases/localidad-f4",
    parent: "dashboard",
  },
  montopuro: {
    label: "Monto Puro F5",
    slug: "/fases/monto-puro-f5",
    parent: "dashboard",
  },
  subset: {
    label: "Subset Sum F6",
    slug: "/fases/subset-global-f6",
    parent: "dashboard",
  },
  finalcleaning: {
    label: "Final Cleaning F7",
    slug: "/fases/final-cleaning-f7",
    parent: "dashboard",
  },
  profunda: {
    label: "Fases Avanzadas",
    slug: "/fases/avanzadas",
    parent: "dashboard",
  },
  configuracion: {
    label: "Ajustes",
    slug: "/configuracion",
    parent: "dashboard",
  },
  reportes: { label: "Reportes", slug: "/reportes", parent: "dashboard" },
};

// Construye la cadena de ancestros hasta la raíz
function buildCrumbs(section: SectionId): { id: SectionId; label: string }[] {
  const crumbs: { id: SectionId; label: string }[] = [];
  let current: SectionId | undefined = section;
  while (current) {
    const info = SECTION_PATHS[current];
    if (!info) break;
    crumbs.unshift({ id: current, label: info.label });
    current = info.parent;
  }
  return crumbs;
}

export default function Breadcrumb() {
  const { activeSection, setActiveSection } = useApp();

  // Dashboard en raíz no necesita breadcrumb
  if (activeSection === "dashboard") return null;

  const crumbs = buildCrumbs(activeSection);

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1 px-1 pb-4 text-sm flex-wrap"
    >
      {/* Inicio siempre visible */}
      <button
        onClick={() => setActiveSection("dashboard")}
        data-href="/dashboard"
        className="flex items-center gap-1 text-muted-foreground hover:text-primary transition-colors"
      >
        <Home className="w-3.5 h-3.5" />
        <span>Inicio</span>
      </button>

      {crumbs.map((crumb, i) => {
        const isLast = i === crumbs.length - 1;
        return (
          <span key={crumb.id} className="flex items-center gap-1">
            <ChevronRight className="w-3.5 h-3.5 text-muted-foreground/50 shrink-0" />
            {isLast ? (
              // Último segmento — no clickeable, resaltado
              <span className="font-semibold text-card-foreground">
                {crumb.label}
              </span>
            ) : (
              // Segmento intermedio — clickeable
              <button
                onClick={() => setActiveSection(crumb.id)}
                data-href={SECTION_PATHS[crumb.id].slug}
                className="text-muted-foreground hover:text-primary transition-colors"
              >
                {crumb.label}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}
