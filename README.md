# 🏦 Motor Automático de Conciliación Contable

> Sistema full-stack para conciliación automática de extractos contables mediante algoritmos de aproximación progresiva. Procesa archivos Excel de hasta 700k+ registros, identifica coincidencias en 5 fases de complejidad creciente y genera reportes detallados por fase.

---

## 📋 Tabla de Contenidos

- [Demo y capturas](#-demo-y-capturas)
- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Stack tecnológico](#-stack-tecnológico)
- [Requisitos previos](#-requisitos-previos)
- [Instalación](#-instalación)
- [Uso](#-uso)
- [API Reference](#-api-reference)
- [Motor de conciliación — Fases](#-motor-de-conciliación--fases)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Estructura del reporte Excel](#-estructura-del-reporte-excel)
- [Configuración avanzada](#-configuración-avanzada)
- [Resultados en producción](#-resultados-en-producción)

---

## ✨ Características

- **5 fases de conciliación progresiva** — desde coincidencias exactas 1:1 hasta monto puro global
- **Procesamiento masivo** — probado con 710.945 registros reales (347.465 post-filtro)
- **Sin errores de punto flotante** — todos los montos se operan en centavos enteros (Int64)
- **Trazabilidad completa** — cada conciliación registra su fase de origen (F1–F5) en la base de datos
- **API REST con polling** — el frontend consulta el progreso cada 5 segundos sin bloquear la UI
- **Reporte Excel con 8 hojas** — desglose por fase: RESUMEN, F1, F2, F3, F4, F5, LOGRADO, PENDIENTES
- **Dashboard con navegación por mes** — filtra historial y estadísticas por período
- **Timeouts configurables** — F2, F3 y F4 tienen límites de tiempo ajustables por request

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│  Dashboard · Ejecutar · Historial · F1–F5 · Reportes   │
└─────────────────┬───────────────────────────────────────┘
                  │  HTTP / REST  (axios + polling 5s)
┌─────────────────▼───────────────────────────────────────┐
│              API REST (FastAPI)                         │
│  POST /upload-and-reconcile/   GET /estado/             │
│  GET  /historial/              GET /stats-por-fase/     │
│  GET  /transacciones/          GET /download-report/    │
└─────────────────┬───────────────────────────────────────┘
                  │  Background Task
┌─────────────────▼───────────────────────────────────────┐
│          Motor de Conciliación (Python)                 │
│                                                         │
│  DataIngestor ──► DatabaseManager ──► ConciliationEngine│
│       │                │                     │         │
│    Polars            SQLite          F1 F2 F3 F4 F5    │
│                                              │         │
│                               ReportGenerator (Excel)  │
└─────────────────────────────────────────────────────────┘
```

El estado del proceso se persiste en **disco** (`estado_proceso.json`) para que el frontend pueda consultar el progreso desde cualquier IP, sin depender del estado en memoria del servidor.

---

## 🛠 Stack tecnológico

### Backend

| Componente | Tecnología | Versión | Rol |
|---|---|---|---|
| Lenguaje | Python | 3.12+ | Runtime principal |
| API | FastAPI + Uvicorn | latest | REST endpoints + ASGI server |
| Ingesta | Polars | latest | Lectura vectorizada del Excel (Rust) |
| Persistencia | SQLite | embebida | Estado de transacciones y conciliaciones |
| Reportes | openpyxl | 3.1.5 | Generación del Excel de 8 hojas |

### Frontend

| Componente | Tecnología | Versión | Rol |
|---|---|---|---|
| Framework | React | 18.3.1 | SPA principal |
| Build tool | Vite | 5.4.19 | Bundler y dev server |
| Lenguaje | TypeScript | 5.8.3 | Tipado estático |
| Estilos | Tailwind CSS | 3.x | Utilidades CSS |
| Componentes UI | shadcn/ui + Radix | latest | Design system |
| HTTP | Axios | 1.13.6 | Llamadas a la API |
| Gráficos | Recharts | 2.15.4 | Charts del dashboard |
| Iconos | Lucide React | latest | Iconografía |

---

## 📦 Requisitos previos

- **Python 3.10+**
- **Node.js 18+**
- **pip** o **uv**

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone <url-del-repo>
cd motor-conciliacion
```

### 2. Backend — instalar dependencias

```bash
pip install fastapi uvicorn polars openpyxl python-multipart
```

### 3. Frontend — instalar dependencias

```bash
cd frontend
npm install
```

---

## ▶️ Uso

### Levantar el backend

```bash
# Desde la raíz del proyecto
uvicorn main_api:app --host 0.0.0.0 --port 8000 --reload
```

La API quedará disponible en `http://localhost:8000`.  
Documentación Swagger en `http://localhost:8000/docs`.

> ⚠️ **Primera ejecución:** la base de datos `conciliacion.db` y la carpeta `reportes/` se crean automáticamente al iniciar el servidor. Si modificas el esquema, elimina `conciliacion.db` y `estado_proceso.json` antes de reiniciar.

### Levantar el frontend

```bash
# En otro terminal, desde la carpeta frontend/
npm run dev
```

La UI quedará disponible en `http://localhost:5173`.

El frontend apunta por defecto al proxy `/api` → `http://localhost:8000`. Si el backend corre en otra IP o puerto, edita `vite.config.ts`:

```ts
server: {
  proxy: {
    '/api': {
      target: 'http://TU_IP:8000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api/, '')
    }
  }
}
```

### Flujo de uso básico

1. Abre el dashboard en el navegador
2. Ve a **Ejecutar Conciliación** y sube el archivo Excel
3. El sistema responde en menos de 1 segundo y comienza a procesar en background
4. La barra de progreso se actualiza automáticamente (polling cada 5 segundos)
5. Al finalizar, el reporte Excel se descarga desde **Reportes** o desde el botón en el Dashboard

---

## 📡 API Reference

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/` | Health check — estado del servidor |
| `POST` | `/upload-and-reconcile/` | Sube Excel y lanza el pipeline. Responde `<1s`. |
| `GET` | `/estado/` | Estado actual del proceso (desde disco) |
| `GET` | `/transacciones/` | Lista paginada. Params: `estado`, `cuenta`, `page`, `limit` |
| `GET` | `/historial/` | Todas las ejecuciones registradas en DB |
| `GET` | `/stats-por-fase/` | Conteos F1–F5 con % sobre conciliados y total. Param: `cuenta` |
| `GET` | `/download-report/{filename}` | Descarga el Excel generado |
| `POST` | `/upload-multi/` | Procesa múltiples períodos acumulados |
| `POST` | `/inferir-fases/` | Infiere `fase_origen` de conciliaciones antiguas marcadas como `F?` |

### Parámetros de configuración en `/upload-and-reconcile/`

```
?f2_timeout=2      # Timeout F2 en segundos (1–10, default: 2)
?f3_timeout=10     # Timeout F3 en segundos (5–30, default: 10)
?f4_timeout=30     # Timeout F4 en segundos (15–120, default: 30)
?max_depth=5       # Profundidad máxima Subset Sum (2–10, default: 5)
```

### Ejemplo de respuesta `/estado/`

```json
{
  "fase": "listo",
  "mensaje": "Conciliación completada",
  "cuenta": "299005060",
  "conciliados": 224822,
  "pendientes": 122643,
  "periodo": "2025/012",
  "reporte": "reportes/reporte_299005060_20260313.xlsx"
}
```

---

## ⚙️ Motor de conciliación — Fases

El motor aplica 5 fases de forma secuencial. Cada fase solo recibe los registros que las anteriores no pudieron conciliar.

```
Excel ──► F0 ──► F1 ──► F2 ──► F3 ──► F4 ──► F5 ──► PENDIENTES
         Filtro  1:1   N:N   ±5cts  Loc   Monto
```

| Fase | Nombre | Algoritmo | Claves de coincidencia |
|---|---|---|---|
| **F0** | Normalización | Polars — filtro SIF82/TES82, cast `Int64×100` | — |
| **F1** | Fast-Pass 1:1 | Join vectorizado O(n log n) | `n_diario` + `localidad` + monto opuesto exacto |
| **F2** | Subset Sum N:N | DP con backtracking, timeout configurable | `n_diario` + `localidad` — grupos que suman cero |
| **F3** | Tolerancia ±5 cts | Fuzzy — diferencia absoluta ≤ 5 centavos | `n_diario` + `localidad` — tolerancia en monto |
| **F4** | Monto + Localidad | Join vectorizado sin `n_diario` | `localidad` + monto opuesto exacto |
| **F5** | Monto Puro Global | SQLite `ROW_NUMBER()` — sin localidad ni `n_diario` | solo monto opuesto exacto |

> **F0 — Filtro de tipos:** el sistema procesa únicamente transacciones de tipo `SIF82` y `TES82`. El resto es descartado en la ingesta.

> **Precisión monetaria:** todos los montos se convierten a centavos enteros (`Int64`) antes de cualquier operación aritmética. El sistema nunca usa `float` para cálculos monetarios.

---

## 📁 Estructura del proyecto

```
motor-conciliacion/
│
├── backend/
│   ├── main_api.py              # Punto de entrada FastAPI
│   ├── conciliacion.db          # Base de datos SQLite (generada en runtime)
│   ├── estado_proceso.json      # Estado del proceso en disco (generado en runtime)
│   ├── reportes/                # Carpeta de reportes Excel (generada en runtime)
│   └── src/
│       ├── api/
│       │   └── routes/
│       │       └── router.py    # Endpoints REST (8 endpoints)
│       └── data/
│           ├── models.py        # Dataclasses: Transaccion, LoteEjecucion, Conciliacion
│           ├── db_manager.py    # Capa de acceso a SQLite
│           ├── ingestor.py      # Lectura y normalización del Excel con Polars
│           ├── engine.py        # Motor de conciliación — F1 a F5
│           └── reporter.py      # Generación del Excel de 8 hojas
│
└── frontend/
    ├── index.html
    ├── vite.config.ts           # Proxy /api → backend
    ├── tailwind.config.ts
    └── src/
        ├── context/
        │   ├── AppContext.tsx           # Navegación de meses, sección activa
        │   └── ReconciliationContext.tsx # Estado global, historial, polling
        ├── sections/
        │   ├── DashboardSection.tsx     # Métricas del mes + gráfico
        │   ├── EjecutarSection.tsx      # Upload + configuración de timeouts
        │   ├── HistorialSection.tsx     # Historial filtrado por mes
        │   ├── FastPassSection.tsx      # Stats F1
        │   ├── SubsetSumSection.tsx     # Stats F2
        │   ├── ToleranciaSection.tsx    # Stats F3
        │   ├── LocalidadSection.tsx     # Stats F4
        │   ├── MontoPuroSection.tsx     # Stats F5
        │   ├── ProfundaSection.tsx      # Resumen F3–F5
        │   ├── ReportesSection.tsx      # 4 reportes diferenciados + descarga
        │   └── ConfiguracionSection.tsx # Ajustes de timeouts y profundidad
        └── components/
            ├── AppSidebar.tsx           # Navegación lateral
            ├── MonthlyNav.tsx           # Header con navegación de meses
            ├── TransaccionesTable.tsx   # Tabla paginada de transacciones
            ├── StatCard.tsx             # Card de métrica reutilizable
            └── ChartSection.tsx         # Gráfico conciliados vs pendientes
```

---

## 📊 Estructura del reporte Excel

El archivo Excel generado contiene **8 hojas**:

| Hoja | Contenido |
|---|---|
| `RESUMEN` | Estadísticas generales y desglose por fase (totales, %, tiempos) |
| `F1` | Transacciones conciliadas por Fast-Pass (coincidencia 1:1 exacta) |
| `F2` | Transacciones conciliadas por Subset Sum (grupos N:N suma cero) |
| `F3` | Transacciones conciliadas por Tolerancia ±5 centavos |
| `F4` | Transacciones conciliadas por Monto + Localidad (sin n_diario) |
| `F5` | Transacciones conciliadas por Monto Puro Global |
| `LOGRADO` | Todas las transacciones conciliadas con columna **Fase** |
| `PENDIENTES` | Todos los registros sin conciliar — para revisión manual |

---

## 🔧 Configuración avanzada

### Variables de entorno (opcional)

```bash
# Puerto del servidor (default: 8000)
PORT=8000

# Ruta de la base de datos (default: conciliacion.db en el directorio de trabajo)
DB_PATH=./conciliacion.db
```

### Límites de configuración de fases

Los timeouts y profundidad se pasan como query params en el request de conciliación. Rangos válidos:

```
f2_timeout:  1 – 10 segundos   (default: 2)
f3_timeout:  5 – 30 segundos   (default: 10)
f4_timeout: 15 – 120 segundos  (default: 30)
max_depth:   2 – 10 niveles    (default: 5)
```

### Reiniciar estado limpio

Si necesitas reprocesar desde cero o cambiaste el esquema de la base de datos:

```bash
# Eliminar estado y base de datos
rm conciliacion.db estado_proceso.json

# Reiniciar el servidor
uvicorn main_api:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📈 Resultados en producción

Procesamiento real sobre `Transitoria_VPA_Diciembre_2025.xlsx`:

| Métrica | Valor |
|---|---|
| Total de registros en el archivo | 710.945 |
| Registros válidos (SIF82 + TES82) | 347.465 |
| Registros conciliados | 224.822 |
| Registros pendientes | 122.643 |
| **Tasa de conciliación** | **64,7%** |
| Cuenta procesada | 299005060 |

---

## ⚠️ Deuda técnica conocida

- **Testing automatizado (RNF03):** no existe cobertura de pruebas. Se recomienda implementar con `pytest` para las 5 fases del motor y `Behave` para escenarios de negocio antes de escalar a producción.
- **Paralelismo por cuenta:** el procesamiento es secuencial (background task). Para volúmenes mayores, considerar `concurrent.futures.ProcessPoolExecutor` por cuenta contable.
