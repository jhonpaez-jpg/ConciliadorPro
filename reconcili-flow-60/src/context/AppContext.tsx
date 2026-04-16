import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";

export type SectionId =
  | "dashboard"
  | "ejecutar"
  | "historial"
  | "programadas"
  | "fastpass"
  | "subsetsum"
  | "finalcleaning"
  | "tolerancia"
  | "localidad"
  | "montopuro"
  | "subset"
  | "profunda"
  | "configuracion"
  | "reportes";

interface AppContextType {
  activeSection: SectionId;
  setActiveSection: (section: SectionId) => void;
  currentMonthIndex: number;
  currentYear: number;
  setMonth: (index: number, year: number) => void;
  nextMonth: () => void;
  prevMonth: () => void;
  isCurrentMonth: () => boolean;
}

const AppContext = createContext<AppContextType | null>(null);

const MONTHS = [
  "ENERO",
  "FEBRERO",
  "MARZO",
  "ABRIL",
  "MAYO",
  "JUNIO",
  "JULIO",
  "AGOSTO",
  "SEPTIEMBRE",
  "OCTUBRE",
  "NOVIEMBRE",
  "DICIEMBRE",
];

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
};

export const getMonthName = (index: number) => MONTHS[index];

// Mapeo sección → segmento URL legible
const SECTION_SLUGS: Record<SectionId, string> = {
  dashboard: "dashboard",
  ejecutar: "ejecutar-conciliacion",
  historial: "historial",
  programadas: "programadas",
  fastpass: "fases/fast-pass-f1",
  subsetsum: "fases/subset-sum-f2",
  tolerancia: "fases/tolerancia-f3",
  localidad: "fases/localidad-f4",
  montopuro: "fases/monto-puro-f5",
  subset: "fases/subset-global-f6",
  finalcleaning: "fases/final-cleaning-f7",
  profunda: "fases/avanzadas",
  configuracion: "configuracion",
  reportes: "reportes",
};

export function AppProvider({ children }: { children: ReactNode }) {
  // Leer sección inicial desde la URL si existe
  const getInitialSection = (): SectionId => {
    const path = window.location.pathname.replace(/^\//, "");
    const found = Object.entries(SECTION_SLUGS).find(
      ([, slug]) => path === slug || path.startsWith(slug),
    );
    return found ? (found[0] as SectionId) : "dashboard";
  };

  const [activeSection, setActiveSectionState] =
    useState<SectionId>(getInitialSection);

  const setActiveSection = (section: SectionId) => {
    setActiveSectionState(section);
    const slug = SECTION_SLUGS[section] ?? section;
    window.history.pushState({ section }, "", `/${slug}`);
  };

  // Sincronizar con botones atrás/adelante del navegador
  useEffect(() => {
    const onPop = () => {
      setActiveSectionState(getInitialSection());
    };
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  const today = new Date();
  const [currentMonthIndex, setCurrentMonthIndex] = useState(today.getMonth());
  const [currentYear, setCurrentYear] = useState(today.getFullYear());

  const isCurrentMonth = (): boolean => {
    const now = new Date();
    return (
      currentMonthIndex === now.getMonth() && currentYear === now.getFullYear()
    );
  };

  const nextMonth = () => {
    if (isCurrentMonth()) return;
    if (currentMonthIndex >= 11) {
      setCurrentMonthIndex(0);
      setCurrentYear((y) => y + 1);
    } else {
      setCurrentMonthIndex((i) => i + 1);
    }
  };

  const prevMonth = () => {
    if (currentMonthIndex <= 0) {
      setCurrentMonthIndex(11);
      setCurrentYear((y) => y - 1);
    } else {
      setCurrentMonthIndex((i) => i - 1);
    }
  };

  const setMonth = (index: number, year: number) => {
    setCurrentMonthIndex(index);
    setCurrentYear(year);
  };

  return (
    <AppContext.Provider
      value={{
        activeSection,
        setActiveSection,
        currentMonthIndex,
        currentYear,
        setMonth,
        nextMonth,
        prevMonth,
        isCurrentMonth,
      }}
    >
      {children}
    </AppContext.Provider>
  );
}
