import { createContext, useContext, useState, ReactNode } from "react";

export type SectionId = 
  | "dashboard" 
  | "ejecutar" 
  | "historial" 
  | "fastpass" 
  | "subsetsum" 
  | "tolerancia"
  | "localidad"
  | "montopuro"
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
  "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
  "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"
];

export const useApp = () => {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
};

export const getMonthName = (index: number) => MONTHS[index];

export function AppProvider({ children }: { children: ReactNode }) {
  const [activeSection, setActiveSection] = useState<SectionId>("dashboard");
  const today = new Date();
  const [currentMonthIndex, setCurrentMonthIndex] = useState(today.getMonth());
  const [currentYear, setCurrentYear] = useState(today.getFullYear());

  const isCurrentMonth = (): boolean => {
    const now = new Date();
    return currentMonthIndex === now.getMonth() && currentYear === now.getFullYear();
  };

  const nextMonth = () => {
    if (isCurrentMonth()) return;
    if (currentMonthIndex >= 11) {
      setCurrentMonthIndex(0);
      setCurrentYear(y => y + 1);
    } else {
      setCurrentMonthIndex(i => i + 1);
    }
  };

  const prevMonth = () => {
    if (currentMonthIndex <= 0) {
      setCurrentMonthIndex(11);
      setCurrentYear(y => y - 1);
    } else {
      setCurrentMonthIndex(i => i - 1);
    }
  };

  const setMonth = (index: number, year: number) => {
    setCurrentMonthIndex(index);
    setCurrentYear(year);
  };

  return (
    <AppContext.Provider value={{
      activeSection, setActiveSection,
      currentMonthIndex, currentYear,
      setMonth, nextMonth, prevMonth, isCurrentMonth
    }}>
      {children}
    </AppContext.Provider>
  );
}
