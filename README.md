# 🏦 Conciliador Pro — Motor Automático de Conciliación Contable

> Sistema full-stack para conciliación automática de extractos contables bancarios. Procesa archivos Excel con transacciones SIF82/TES82 mediante 8 fases de algoritmos de programación dinámica, genera reportes detallados por fase y soporta múltiples usuarios concurrentes con base de datos remota.

---

## 📋 Tabla de Contenidos

- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Stack tecnológico](#-stack-tecnológico)
- [Requisitos previos](#-requisitos-previos)
- [Inicio rápido — archivos .bat](#-inicio-rápido--archivos-bat)
- [Inicio manual — paso a paso](#-inicio-manual--paso-a-paso)
- [Configuración de base de datos](#-configuración-de-base-de-datos)
- [Motor de conciliación — 8 fases](#-motor-de-conciliación--8-fases)
- [API Reference](#-api-reference)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Estructura del reporte Excel](#-estructura-del-reporte-excel)
- [Concurrencia multi-usuario](#-concurrencia-multi-usuario)
- [Notificaciones PWA](#-notificaciones-pwa)
- [Configuración avanzada](#-configuración-avanzada)
- [Resultados en producción](#-resultados-en-producción)
- [Despliegue](#-despliegue)

---

## ✨ Características

- **8 fases de conciliación progresiva** — F1 Fast-Pass hasta F7b Final Cleaning
- **Procesamiento masivo** — probado con 710.945 registros reales
- **Sin errores de punto flotante** — todos los montos operados en centavos enteros (Int64)
- **Multi-usuario concurrente** — estado por `id_lote` en DB, sin interferencia entre sesiones
- **3 motores de DB** — SQLite local, MySQL o PostgreSQL remoto via `DATABASE_URL`
- **Reportes portables** — Excel regenerado desde la DB si el archivo no existe localmente
- **Ejecuciones programadas** — scheduler nocturno con cola y notificaciones
- **PWA con notificaciones** — toast in-app + notificaciones del OS via Service Worker
- **Historial completo** — COMPLETADO / CANCELADO / ERROR con badges visuales
- **HTTPS en red local** — certificado self-signed para notificaciones bajo IP de red

---

## 🏗 Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                  │
│  Dashboard · Ejecutar · Historial · Programadas · F1–F7b   │
│  Notificaciones PWA · Reportes · Configuración             │
└─────────────────┬───────────────────────────────────────────┘
                  │  HTTPS / REST  (axios + polling 5s por id_lote)
┌─────────────────▼───────────────────────────────────────────┐
│              API REST (FastAPI + Uvicorn)                   │
│  POST /upload-and-reconcile/  → devuelve id_lote           │
│  GET  /estado/?id_lote=X      → estado del proceso         │
│  POST /cancelar/?id_lote=X    → cancela proceso            │
│  GET  /historial/             → todas las ejecuciones      │
│  GET  /programadas/           → ejecuciones programadas    │
│  GET  /stats-por-fase/        → desglose F1–F7b            │
│  GET  /download-report/{f}    → Excel (regenera si falta)  │
└─────────────────┬───────────────────────────────────────────┘
                  │  Background Task (hilo daemon)
┌─────────────────▼───────────────────────────────────────────┐
│          Motor de Conciliación (Python puro)                │
│                                                             │
│  DataIngestor ──► DatabaseManager ──► ReconciliationEngine  │
│       │                │                     │             │
│    Polars         SQLAlchemy          F1 F2 F3 F4           │
│                   (MySQL/PG/SQLite)   F5 F6 F7 F7b          │
│                                              │             │
│                               ReconciliationReporter       │
│                               (Excel streaming + PDF)      │
└─────────────────────────────────────────────────────────────┘
```

El estado de cada proceso se persiste en la tabla `proceso_estado` de la DB, identificado por `id_lote` único (microsegundos). Esto permite múltiples usuarios concurrentes sin interferencia.

---

## 🛠 Stack tecnológico

### Backend

| Componente | Tecnología | Rol |
|---|---|---|
| Lenguaje | Python 3.10+ | Runtime principal |
| API | FastAPI + Uvicorn | REST endpoints + ASGI server |
| Ingesta | Polars | Lectura vectorizada del Excel (Rust) |
| ORM / DB | SQLAlchemy 2.0 | Abstracción multi-motor |
| DB local | SQLite (embebida) | Desarrollo sin configuración |
| DB remota | MySQL / PostgreSQL | Producción / Railway |
| Reportes Excel | xlsxwriter | Generación streaming 8 hojas |
| Reportes PDF | reportlab | PDF profesional desde DB |
| Entorno | python-dotenv | Variables de entorno |

### Frontend

| Componente | Tecnología | Rol |
|---|---|---|
| Framework | React 18 | SPA principal |
| Build tool | Vite 5 | Bundler + dev server + HTTPS |
| Lenguaje | TypeScript 5 | Tipado estático |
| Estilos | Tailwind CSS 3 | Utilidades CSS |
| Componentes UI | shadcn/ui + Radix | Design system |
| HTTP | Axios | Llamadas a la API |
| Gráficos | Recharts | Charts del dashboard |
| Iconos | Lucide React | Iconografía |
| PWA | Service Worker | Notificaciones en background |
| SSL local | @vitejs/plugin-basic-ssl | HTTPS en red local |

---

## 📦 Requisitos previos

- **Python 3.10+** — [python.org](https://python.org)
- **Node.js 18+** — [nodejs.org](https://nodejs.org)
- **pip** (incluido con Python)

Para base de datos remota (opcional):
- Cuenta en [Railway](https://railway.app), [PlanetScale](https://planetscale.com) u otro proveedor MySQL/PostgreSQL

---

## ⚡ Inicio rápido — archivos .bat

La forma más simple. Los `.bat` detectan automáticamente si el entorno virtual es válido para la ruta actual y lo recrean si es necesario.

### 1. Iniciar el backend

```
Doble clic en:
Motor_Conciliaciones\start_server.bat
```

El script:
1. Verifica que Python esté instalado
2. Detecta si el `venv` es válido para esta ruta (importante al mover la carpeta entre equipos)
3. Si no es válido, lo borra y recrea automáticamente
4. Instala todas las dependencias de `requirements.txt`
5. Arranca uvicorn en `http://0.0.0.0:8000`

### 2. Iniciar el frontend

```
Doble clic en:
reconcili-flow-60\start_frontend.bat
```

El script:
1. Verifica que Node.js esté instalado
2. Instala dependencias npm si `node_modules` no existe
3. Arranca Vite en `https://localhost:8080` (HTTPS para notificaciones)

### 3. Abrir la aplicación

- **Local:** `https://localhost:8080`
- **Red local:** `https://192.168.X.X:8080`

> La primera vez el navegador mostrará advertencia de certificado no confiable. Haz clic en **Avanzado → Continuar** — es el certificado self-signed de desarrollo.

---

## 🔧 Inicio manual — paso a paso

### Backend

```bash
# 1. Entrar a la carpeta del backend
cd Motor_Conciliaciones

# 2. Crear entorno virtual
python -m venv venv

# 3. Activar el entorno virtual
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 4. Instalar dependencias
pip install -r requirements.txt

# 5. (Opcional) Configurar base de datos remota
# Crear archivo .env con la URL de conexión:
echo DATABASE_URL=mysql+pymysql://user:pass@host:3306/db > .env

# 6. Iniciar el servidor
uvicorn src.api.main_api:app --host 0.0.0.0 --port 8000 --reload
```

La API queda disponible en `http://localhost:8000`.  
Documentación Swagger en `http://localhost:8000/docs`.

### Frontend

```bash
# 1. Entrar a la carpeta del frontend
cd reconcili-flow-60

# 2. Instalar dependencias
npm install

# 3. Iniciar el servidor de desarrollo
npm run dev
```

La UI queda disponible en `https://localhost:8080`.

Si el backend corre en otra IP o puerto, edita `vite.config.ts`:

```ts
proxy: {
  '/api': {
    target: 'http://TU_IP:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, '')
  }
}
```

---

## 🗄 Configuración de base de datos

El sistema soporta 3 motores sin cambiar ningún código. Solo cambia el archivo `.env` en `Motor_Conciliaciones/`.

### SQLite local (default — sin configuración)

No requiere ningún archivo `.env`. Al arrancar el servidor se crea `conciliacion.db` automáticamente.

```
# Sin .env → SQLite automático
```

### MySQL remoto

```env
# Motor_Conciliaciones/.env
DATABASE_URL=mysql+pymysql://usuario:contraseña@host:3306/nombre_db
```

Dependencias necesarias (ya en `requirements.txt`):
```bash
pip install pymysql cryptography
```

### PostgreSQL remoto (Railway, Supabase, Neon)

```env
# Motor_Conciliaciones/.env
DATABASE_URL=postgresql://usuario:contraseña@host:5432/nombre_db
```

> Railway provee `DATABASE_URL` automáticamente en el panel de Variables del servicio PostgreSQL. No hay que configurar nada más al desplegar.

### Tablas creadas automáticamente

Al arrancar el servidor, `inicializar_tablas()` crea las siguientes tablas si no existen:

| Tabla | Descripción |
|---|---|
| `transaccion` | Registros del Excel con estado (PENDIENTE / CONCILIADO) |
| `conciliacion` | Grupos conciliados con fase de origen (F1–F7b) |
| `historial_ejecucion` | Registro permanente de cada ejecución (COMPLETADO / CANCELADO / ERROR) |
| `ejecucion_programada` | Cola de ejecuciones nocturnas |
| `proceso_estado` | Estado en tiempo real por `id_lote` (multi-usuario) |
| `lote_ejecucion` | Metadatos de cada lote de procesamiento |

---

## ⚙️ Motor de conciliación — 8 fases

El motor aplica las fases secuencialmente. Cada fase solo recibe los registros que las anteriores no pudieron conciliar.

```
Excel ──► F1 ──► F2 ──► F3 ──► F4 ──► F6 ──► F7 ──► F7b ──► F5 ──► PENDIENTES
         1:1   N:N   ±5cts  Loc   N→1   1→N   Lim   Monto
```

| Fase | Nombre | Algoritmo | Claves de coincidencia |
|---|---|---|---|
| **F1** | Fast-Pass 1:1 | Join vectorizado O(n log n) | `n_diario` + `localidad` + monto opuesto exacto |
| **F2** | Subset Sum N:N | DP con backtracking, timeout configurable | `n_diario` + `localidad` — grupos que suman cero |
| **F3** | Tolerancia ±5 cts | Fuzzy — diferencia absoluta ≤ 5 centavos | `n_diario` + `localidad` — tolerancia en monto |
| **F4** | Monto + Localidad | Join vectorizado sin `n_diario` | `localidad` + monto opuesto exacto |
| **F6** | Subset Sum Global | DP — N positivos → 1 negativo (umbral >500K) | Global — sin localidad ni n_diario |
| **F7** | Final Cleaning | DP — 1 positivo → N negativos | Global — positivos ASC |
| **F7b** | Final Cleaning B | DP — positivos restantes → N negativos | Global — poda temprana |
| **F5** | Monto Puro | `ROW_NUMBER()` SQL — último recurso | Solo monto opuesto exacto |

> **Precisión monetaria:** todos los montos se convierten a centavos enteros (`Int64`) antes de cualquier operación. El sistema nunca usa `float` para cálculos monetarios.

> **Orden del pipeline:** F1→F4 por localidad → F6/F7/F7b global → F5 último recurso.

---

## 📡 API Reference

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/api/validar-archivo/` | Valida período único antes de ejecutar |
| `POST` | `/api/upload-and-reconcile/` | Sube Excel y lanza pipeline. Devuelve `id_lote` |
| `GET` | `/api/estado/?id_lote=X` | Estado del proceso por `id_lote` |
| `POST` | `/api/cancelar/?id_lote=X` | Cancela proceso activo |
| `POST` | `/api/programar/` | Programa ejecución nocturna |
| `GET` | `/api/programadas/` | Lista ejecuciones programadas |
| `DELETE` | `/api/programadas/{id}` | Cancela ejecución programada |
| `GET` | `/api/historial/` | Todas las ejecuciones registradas |
| `GET` | `/api/stats-por-fase/` | Conteos F1–F7b. Params: `cuenta`, `id_lote` |
| `GET` | `/api/transacciones/` | Lista paginada. Params: `estado`, `cuenta`, `page` |
| `GET` | `/api/download-report/{filename}` | Descarga Excel (regenera desde DB si falta) |
| `GET` | `/api/download-report-pdf/{filename}` | Descarga PDF profesional |

### Parámetros de `/upload-and-reconcile/`

```
?f2_timeout=2      # Timeout F2 en segundos (1–10, default: 2)
?f3_timeout=10     # Timeout F3 en segundos (5–30, default: 10)
?f4_timeout=30     # Timeout F4 en segundos (15–120, default: 30)
?max_depth=5       # Profundidad máxima Subset Sum (2–10, default: 5)
```

### Respuesta de `/api/upload-and-reconcile/`

```json
{
  "status": "aceptado",
  "id_lote": 1776358801234567,
  "mensaje": "Proceso iniciado. Consulta GET /estado/?id_lote=...",
  "archivo": "NOV 2025.xlsx"
}
```

### Respuesta de `/api/estado/?id_lote=X`

```json
{
  "fase": "listo",
  "mensaje": "Completado en 47s",
  "cuenta": "299005060",
  "conciliados": 27263,
  "pendientes": 3624,
  "tasa": 88.27,
  "reporte": "resultado_conciliacion_20260416_122204.xlsx",
  "periodo": "2025/012",
  "id_lote": 1776358801234567
}
```

---

## 📁 Estructura del proyecto

```
CONCILIACION MENSUAL/
│
├── README.md                          # Este archivo
│
├── Motor_Conciliaciones/              # Backend Python
│   ├── start_server.bat               # ⚡ Inicio rápido Windows
│   ├── requirements.txt               # Dependencias Python
│   ├── .env                           # DATABASE_URL (no subir a git)
│   ├── .gitignore
│   ├── data_samples/                  # Archivos Excel temporales
│   │   └── programados/               # Archivos de ejecuciones programadas
│   ├── reportes/                      # Reportes Excel/PDF generados
│   └── src/
│       ├── api/
│       │   ├── main_api.py            # Punto de entrada FastAPI
│       │   ├── routes.py              # Todos los endpoints REST
│       │   └── report_routes.py       # Endpoints de reportes especializados
│       ├── core/
│       │   ├── engine.py              # Motor F1–F7b (programación dinámica)
│       │   └── models.py              # Dataclass Transaccion
│       ├── data/
│       │   ├── db_connection.py       # Engine SQLAlchemy multi-motor
│       │   ├── db_manager.py          # Capa de acceso a datos
│       │   └── ingestor.py            # Lectura y normalización Excel con Polars
│       └── utils/
│           └── reporter.py            # Generación Excel streaming + PDF
│
└── reconcili-flow-60/                 # Frontend React
    ├── start_frontend.bat             # ⚡ Inicio rápido Windows
    ├── package.json
    ├── vite.config.ts                 # Proxy /api + HTTPS
    ├── public/
    │   └── sw.js                      # Service Worker (notificaciones PWA)
    └── src/
        ├── context/
        │   ├── AppContext.tsx          # Navegación de meses, sección activa
        │   └── ReconciliationContext.tsx # Estado global, historial, polling
        ├── hooks/
        │   ├── useNotifications.ts    # SW + toast in-app dual
        │   └── useStatsForLote.ts     # Stats por id_lote
        ├── components/
        │   ├── AppNotification.tsx    # Toast in-app animado (verde/violeta/rojo)
        │   ├── AppSidebar.tsx
        │   ├── MonthlyNav.tsx
        │   ├── TransaccionesTable.tsx
        │   ├── StatCard.tsx
        │   └── ChartSection.tsx
        ├── sections/
        │   ├── DashboardSection.tsx
        │   ├── EjecutarSection.tsx
        │   ├── HistorialSection.tsx   # Badges COMPLETADO/CANCELADO/ERROR
        │   ├── ProgramadasSection.tsx # Monitor en tiempo real
        │   ├── FastPassSection.tsx    # Stats F1
        │   ├── SubsetSumSection.tsx   # Stats F2
        │   ├── ToleranciaSection.tsx  # Stats F3
        │   ├── LocalidadSection.tsx   # Stats F4
        │   ├── MontoPuroSection.tsx   # Stats F5
        │   ├── SubsetSection.tsx      # Stats F6
        │   ├── FinalCleaningSection.tsx # Stats F7/F7b
        │   ├── ReportesSection.tsx
        │   └── ConfiguracionSection.tsx
        └── pages/
            └── Index.tsx
```

---

## 📊 Estructura del reporte Excel

El archivo Excel generado contiene **10 hojas**:

| Hoja | Contenido |
|---|---|
| `RESUMEN` | Estadísticas generales y desglose por fase |
| `F1` | Transacciones conciliadas por Fast-Pass (1:1 exacto) |
| `F2` | Transacciones conciliadas por Subset Sum (N:N suma cero) |
| `F3` | Transacciones conciliadas por Tolerancia ±5 centavos |
| `F4` | Transacciones conciliadas por Monto + Localidad |
| `F5` | Transacciones conciliadas por Monto Puro Global |
| `F6` | Transacciones conciliadas por Subset Sum Global (N→1) |
| `F7` | Transacciones conciliadas por Final Cleaning (1→N) |
| `LOGRADO` | Todas las transacciones conciliadas con columna Fase |
| `PENDIENTES` | Todos los registros sin conciliar — para revisión manual |

---

## 👥 Concurrencia multi-usuario

El sistema soporta múltiples usuarios simultáneos sin login ni autenticación.

**Cómo funciona:**

1. Cada vez que un usuario sube un archivo, el backend genera un `id_lote` único en microsegundos (`time.time_ns() // 1000`)
2. El `id_lote` se devuelve al frontend y se guarda en `sessionStorage` del navegador
3. Cada navegador tiene su propio `sessionStorage` — completamente aislado
4. El frontend usa ese `id_lote` para todas las consultas de estado y cancelación
5. El estado se persiste en la tabla `proceso_estado` de la DB, una fila por `id_lote`

```
PC-A → sube archivo → id_lote = 1776358801234001
PC-B → sube archivo → id_lote = 1776358801234892
         ↑ misma red, diferente navegador, diferente sessionStorage
```

Incluso dos pestañas del mismo navegador tienen `sessionStorage` independiente.

**Ejecuciones programadas:** el scheduler usa un `threading.Lock()` para ejecutar una conciliación a la vez en cola, evitando contención en la DB.

---

## 🔔 Notificaciones PWA

El sistema envía notificaciones en dos modos:

| Situación | Comportamiento |
|---|---|
| Pestaña **visible** | Toast in-app animado (esquina inferior derecha) |
| Pestaña **oculta** / navegador minimizado | Notificación del OS via Service Worker |

**Eventos que generan notificación:**
- ✅ Conciliación completada
- 📅 Ejecución programada creada
- ⚙️ Ejecución programada iniciada
- ✅ Ejecución programada completada
- ❌ Error en ejecución programada

**Activar notificaciones:**
1. Ve a **Ajustes** en la barra lateral
2. En la sección "Notificaciones", haz clic en **Activar**
3. Acepta el permiso del navegador

**Nota sobre red local:** las notificaciones del OS requieren HTTPS. El frontend corre en HTTPS con certificado self-signed. La primera vez el navegador mostrará una advertencia — acepta para continuar.

---

## 🔧 Configuración avanzada

### Límites de fases (query params)

```
f2_timeout:  1 – 10 segundos   (default: 2)
f3_timeout:  5 – 30 segundos   (default: 10)
f4_timeout: 15 – 120 segundos  (default: 30)
max_depth:   2 – 10 niveles    (default: 5)
```

### Mover el proyecto entre equipos

Al mover la carpeta a otro equipo, el `venv` tiene rutas absolutas del equipo original. El `start_server.bat` lo detecta automáticamente y recrea el entorno. Solo necesitas tener Python instalado en el nuevo equipo.

### Reiniciar estado limpio (SQLite)

```bash
# Eliminar base de datos local
del Motor_Conciliaciones\conciliacion.db

# Reiniciar el servidor — las tablas se recrean automáticamente
```

Para MySQL/PostgreSQL, las tablas se recrean con `CREATE TABLE IF NOT EXISTS` al arrancar.

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
| Tiempo de procesamiento | ~47 segundos |

---

## 🚀 Despliegue

### Backend en Railway / Render / Fly.io

1. Conecta el repositorio
2. Configura la variable de entorno `DATABASE_URL` con la URL de tu base de datos
3. El comando de inicio es: `uvicorn src.api.main_api:app --host 0.0.0.0 --port $PORT`
4. Las tablas se crean automáticamente al primer arranque

### Frontend en Vercel / Netlify

1. Directorio raíz: `reconcili-flow-60`
2. Comando de build: `npm run build`
3. Directorio de salida: `dist`
4. Configura la variable de entorno `VITE_API_URL` si el backend está en otro dominio

### Variables de entorno en producción

```env
# Backend
DATABASE_URL=postgresql://user:pass@host:5432/db   # Railway lo inyecta automáticamente

# Frontend (vite.config.ts)
# El proxy /api apunta al backend — ajustar target en producción
```

---

## ⚠️ Notas técnicas

- **`estado_proceso.json`** ya no se usa — el estado se persiste en la tabla `proceso_estado` de la DB
- **Reportes portables** — la DB guarda solo el nombre del archivo, no la ruta absoluta. Si el archivo no existe localmente, se regenera desde la DB automáticamente
- **MySQL en Linux** — los nombres de tablas son en minúsculas (case-sensitive en Linux). El código usa minúsculas en todas las queries
- **`INTEGER` vs `BIGINT`** — `id_lote` y `monto_centavos` son `BIGINT` en MySQL/PostgreSQL para evitar overflow con timestamps en microsegundos y montos grandes
- **Testing** — no existe cobertura de pruebas automatizadas. Se recomienda `pytest` para el motor y `Behave` para escenarios de negocio antes de escalar a producción
