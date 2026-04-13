import { AppProvider, useApp } from "@/context/AppContext";
import { ReconciliationProvider } from "@/context/ReconciliationContext";
import AppSidebar from "@/components/AppSidebar";
import MonthlyNav from "@/components/MonthlyNav";
import FloatingIcons from "@/components/FloatingIcons";
import ChatBot from "@/components/ChatBot";
import Breadcrumb from "@/components/Breadcrumb";
import LinkPreview from "@/components/LinkPreview";
import DashboardSection from "@/sections/DashboardSection";
import EjecutarSection from "@/sections/EjecutarSection";
import HistorialSection from "@/sections/HistorialSection";
import ProgramadasSection from "@/sections/ProgramadasSection";
import FastPassSection from "@/sections/FastPassSection";
import SubsetSumSection from "@/sections/SubsetSumSection";
import FinalCleaningSection from "@/sections/FinalCleaningSection";
import ToleranciaSection from "@/sections/ToleranciaSection";
import LocalidadSection from "@/sections/LocalidadSection";
import MontoPuroSection from "@/sections/MontoPuroSection";
import SubsetSection from "@/sections/SubsetSection";
import ProfundaSection from "@/sections/ProfundaSection";
import ConfiguracionSection from "@/sections/ConfiguracionSection";
import ReportesSection from "@/sections/ReportesSection";

function SectionRouter() {
  const { activeSection } = useApp();

  const sections: Record<string, React.ReactNode> = {
    dashboard: <DashboardSection />,
    ejecutar: <EjecutarSection />,
    historial: <HistorialSection />,
    programadas: <ProgramadasSection />,
    fastpass: <FastPassSection />,
    subsetsum: <SubsetSumSection />,
    tolerancia: <ToleranciaSection />,
    localidad: <LocalidadSection />,
    montopuro: <MontoPuroSection />,
    subset: <SubsetSection />,
    profunda: <ProfundaSection />,
    finalcleaning: <FinalCleaningSection />,
    configuracion: <ConfiguracionSection />,
    reportes: <ReportesSection />,
  };

  return <>{sections[activeSection] || <DashboardSection />}</>;
}

function AppLayout() {
  return (
    <div className="h-screen gradient-bg p-5 relative overflow-hidden">
      <FloatingIcons />
      <div className="max-w-[1600px] h-[calc(100vh-40px)] mx-auto glass-container rounded-[32px] shadow-container overflow-hidden relative z-10 flex flex-col">
        <MonthlyNav />
        <div className="flex flex-1 min-h-0 overflow-hidden">
          <AppSidebar />
          <main className="flex-1 p-8 overflow-y-auto custom-scrollbar" style={{ background: "#f8fafd" }}>
            <Breadcrumb />
            <SectionRouter />
          </main>
        </div>
      </div>
      <ChatBot />
      <LinkPreview />
    </div>
  );
}

const Index = () => (
  <AppProvider>
    <ReconciliationProvider>
      <AppLayout />
    </ReconciliationProvider>
  </AppProvider>
);

export default Index;
