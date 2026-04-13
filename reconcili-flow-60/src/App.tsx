import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Index from "./pages/Index";

const queryClient = new QueryClient();

// Todas las rutas de la app sirven Index — la sección activa se lee desde la URL en AppContext
const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/"                        element={<Index />} />
          <Route path="/dashboard"               element={<Index />} />
          <Route path="/ejecutar"                element={<Index />} />
          <Route path="/historial"               element={<Index />} />
          <Route path="/programadas"             element={<Index />} />
          <Route path="/fases/*"                 element={<Index />} />
          <Route path="/configuracion"           element={<Index />} />
          <Route path="/reportes"                element={<Index />} />
          {/* Cualquier ruta desconocida → raíz */}
          <Route path="*"                        element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
