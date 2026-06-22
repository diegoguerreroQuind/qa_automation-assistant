# Contexto de Frontend — QA AI Assistant

> Guía integral para el desarrollo del frontend de **QA AI Assistant**: una
> herramienta interna que convierte una colección Postman + una HU de Jira en
> un proyecto Cypress BDD completo, generado por IA y descargable como ZIP.

Este documento es la **fuente única de verdad** sobre decisiones arquitectónicas,
tecnologías, convenciones y lineamientos de implementación. Cualquier desarrollador
debe poder leerlo, entender el alcance y empezar a contribuir sin contexto previo.

---

## Tabla de contenidos

1. [Propósito de la aplicación](#1-propósito-de-la-aplicación)
2. [Visión general del backend (qué consume el frontend)](#2-visión-general-del-backend)
3. [Stack tecnológico](#3-stack-tecnológico)
4. [Librerías recomendadas y justificación](#4-librerías-recomendadas-y-justificación)
5. [Principios y estándares de desarrollo](#5-principios-y-estándares-de-desarrollo)
6. [Arquitectura del proyecto](#6-arquitectura-del-proyecto)
7. [Convenciones de código y nomenclatura](#7-convenciones-de-código-y-nomenclatura)
8. [Consumo de API](#8-consumo-de-api)
9. [Manejo de estado](#9-manejo-de-estado)
10. [Roles, permisos y rutas protegidas (RBAC)](#10-roles-permisos-y-rutas-protegidas-rbac)
11. [Integración con WebSocket](#11-integración-con-websocket)
12. [Diseño UI/UX y accesibilidad](#12-diseño-uiux-y-accesibilidad)
13. [Setup inicial del proyecto](#13-setup-inicial-del-proyecto)
14. [Flujos funcionales que el frontend debe soportar](#14-flujos-funcionales-que-el-frontend-debe-soportar)
15. [Checklist de calidad antes de cada PR](#15-checklist-de-calidad-antes-de-cada-pr)

---

## 1. Propósito de la aplicación

**QA AI Assistant** automatiza la creación de pruebas E2E para APIs internas.
El usuario QA:

1. Sube una **colección Postman** (sus endpoints).
2. Selecciona una **HU de Jira** (criterios de aceptación).
3. La IA cruza ambos y genera un proyecto **Cypress BDD** (Gherkin + TypeScript)
   listo para ejecutar con `npm install && npm test`.

El frontend es el **panel de control** de todo ese pipeline: autenticación,
gestión de proyectos, navegación de HUs, ejecución del pipeline paso a paso,
visualización del progreso en vivo y descarga del entregable.

---

## 2. Visión general del backend

El backend es una **API REST + WebSocket** construida con FastAPI. El frontend
consumirá los siguientes recursos:

### Endpoints por dominio

| Dominio | Endpoints |
|---|---|
| **Auth** | `POST /auth/register` · `POST /auth/login` · `GET /auth/me` · `POST /auth/logout` |
| **Credentials** | `PUT /credentials` · `GET /credentials` · `DELETE /credentials/{provider}/{key}` |
| **Projects** | `POST /projects` · `GET /projects` · `GET /projects/{id}` · `GET /projects/{id}/executions` · `DELETE /projects/{id}` |
| **Jira HUs** | `POST /jira/tickets` · `GET /jira/tickets` · `POST /jira/tickets/{key}` |
| **Pipeline** | `POST /executions` · `POST /executions/{id}/upload` (multipart) · `POST /executions/{id}/extract` · `POST /executions/{id}/fetch-jira` · `GET /executions/{id}/endpoints` · `PATCH /executions/{id}/endpoints` · `POST /executions/{id}/generate` · `GET /executions/{id}` |
| **Files** | `GET /executions/{id}/files` · `GET /executions/{id}/files/{name}` · `PATCH /executions/{id}/files/{name}` · `GET /executions/{id}/download` (ZIP) |
| **WebSocket** | `ws://.../ws/executions/{id}?token=<JWT>` |
| **Health** | `GET /health` |

### Autenticación

- **JWT Bearer** firmado con HS256, válido **12 horas**.
- Se obtiene en `POST /auth/login` y se envía como `Authorization: Bearer <jwt>` en todos los endpoints (excepto `/health`, `/auth/login`, `/auth/register`).
- Existe **Token Revocation List (TRL)** en Redis: si el usuario hace `POST /auth/logout`, el JWT queda inválido aunque no haya expirado.

### Roles del backend

```
admin  → puede ver/eliminar cualquier proyecto, gestionar usuarios
qa     → solo sus propios proyectos y ejecuciones (default al registrar)
```

El payload del JWT contiene `sub` (user_id) y `email`, pero **no el rol**. El frontend
obtiene el rol consultando `GET /auth/me` al iniciar sesión.

### Estados de ejecución del pipeline

```
pending → extracting → generating → complete | partial | failed
```

`partial` significa que algunos endpoints fallaron en la generación pero otros no.
Mostrar siempre claramente cuáles fallaron y permitir re-generar.

### Códigos HTTP y mensajes esperables

| Código | Cuándo se ve | UI debe |
|---|---|---|
| `400` | Validación de negocio (ej. generate sin endpoints seleccionados) | mostrar mensaje del `detail` |
| `401` | Token inválido o expirado | redirigir a `/login` y limpiar sesión |
| `403` | Acceso denegado (path traversal, recurso de otro user en WS) | toast de error |
| `404` | Recurso no existe | mostrar estado vacío |
| `409` | Orden incorrecto (ej. `fetch-jira` antes de `extract`) | mostrar pasos faltantes |
| `413` | Archivo demasiado grande (>10MB) | bloquear input con mensaje |
| `422` | Validación de schema (Pydantic) | resaltar campo del form |
| `424` | Dependencia faltante (ej. credenciales Jira no guardadas) | redirigir a settings |
| `502` | Error consultando Jira (red, token revocado) | toast con sugerencia |

---

## 3. Stack tecnológico

| Tecnología | Versión recomendada | Rol |
|---|---|---|
| **React** | 18.x | Librería UI |
| **Vite** | 5.x | Build tool / dev server |
| **TypeScript** | 5.x | Tipado estático estricto |
| **Tailwind CSS** | 3.x | Estilos utilitarios + diseño consistente |
| **Node** | ≥ 20 LTS | Runtime de build |
| **pnpm** | latest | Gestor de paquetes (más rápido y eficiente que npm) |

**Razones del stack:**

- **React + Vite**: HMR instantáneo, build optimizado, ecosistema masivo.
- **TypeScript estricto**: detecta clases enteras de bugs en compile-time y documenta
  los contratos con el backend (los tipos `FastAPI Pydantic` se replican como `interface`/`type`).
- **Tailwind**: estilo consistente, sin nombrar clases CSS, sin archivos `.css` regados.

Tecnologías **descartadas explícitamente**:
- ❌ Next.js — no necesitamos SSR para una app interna autenticada.
- ❌ Redux Toolkit — sobra; Zustand + React Query cubren todo.
- ❌ MUI / Ant Design — diseño no extensible; usaremos shadcn/ui (más control).

---

## 4. Librerías recomendadas y justificación

### Capa de datos y comunicación

| Librería | Versión | Propósito |
|---|---|---|
| **axios** | ^1.7 | Cliente HTTP con interceptores. Más expresivo que `fetch` para auth, refresh, errores globales. |
| **@tanstack/react-query** | ^5 | Caché de estado del servidor, refetch automático, invalidación, optimistic updates, retry. Reemplaza el 80% del estado global. |

### Navegación

| Librería | Versión | Propósito |
|---|---|---|
| **react-router-dom** | ^6.26 | Routing declarativo + data routers + lazy loading. |

### Estado del cliente

| Librería | Versión | Propósito |
|---|---|---|
| **zustand** | ^4.5 | Estado global pequeño y reactivo. Sin boilerplate. Solo para sesión y UI compartida. |

### Formularios y validación

| Librería | Versión | Propósito |
|---|---|---|
| **react-hook-form** | ^7.53 | Formularios performantes (no re-render por keystroke). |
| **zod** | ^3.23 | Validación de schemas TypeScript-first. Se comparte entre formularios y respuestas de API. |
| **@hookform/resolvers** | ^3.9 | Adaptador entre RHF y Zod. |

### UI y componentes

| Librería | Versión | Propósito |
|---|---|---|
| **shadcn/ui** | latest (copy-paste) | Componentes accesibles (Radix UI) personalizables. No es paquete: vive en `src/components/ui/`. |
| **lucide-react** | ^0.460 | Iconografía consistente, tree-shakeable. |
| **sonner** | ^1.5 | Notificaciones toast (mejor UX y accesibilidad que react-toastify). |
| **framer-motion** | ^11 | Animaciones declarativas (transiciones, listas, layouts). |
| **clsx** + **tailwind-merge** | latest | Combinar clases Tailwind condicionalmente sin conflictos (envueltas en helper `cn()`). |

### Datos y visualización

| Librería | Versión | Propósito |
|---|---|---|
| **recharts** | ^2.13 | Gráficas (ej. dashboard de ejecuciones por estado, tiempo promedio de generación). |
| **date-fns** | ^4 | Formateo y manipulación de fechas. Tree-shakeable, mejor que moment. |

### Quality tooling (dev)

| Librería | Propósito |
|---|---|
| **eslint** + **eslint-plugin-react** + **@typescript-eslint** | Linting estricto. |
| **prettier** | Formato consistente. |
| **vitest** + **@testing-library/react** | Tests unitarios y de componentes. |
| **husky** + **lint-staged** | Pre-commit checks. |

---

## 5. Principios y estándares de desarrollo

### Clean Code

- **Nombres expresivos**: `loadProjectsByUser()` mejor que `fetch()`.
- **Funciones cortas**: una función = una responsabilidad. Si supera 30-40 líneas, dividir.
- **Sin números/strings mágicos**: extraer a `constants/`.
- **Sin código comentado**: si no se usa, se borra (Git tiene memoria).

### SOLID (aplicado a UI)

- **S** — Single Responsibility: un componente hace UNA cosa visual. Si un `ExecutionPanel`
  hace fetching + render + lógica de selección → dividir en `useExecution` (hook),
  `ExecutionView` (presentacional), `EndpointSelector` (interactivo).
- **O** — Open/Closed: componentes extensibles por `props`, no por modificación.
- **L** — Liskov: si exportas un `<Button>`, todas sus variantes deben respetar la API base.
- **I** — Interface Segregation: tipos pequeños y específicos (`ButtonProps` distinto de `IconButtonProps`).
- **D** — Dependency Inversion: los componentes dependen de **hooks** (abstracción), no de Axios directo.

### Separation of Concerns

```
components/        → presentación (no fetching, no lógica de negocio)
hooks/             → lógica reusable
services/          → comunicación con el backend
store/             → estado global del cliente
features/<X>/      → vertical completo de una funcionalidad
```

### Otros principios

- **Composición sobre herencia**: en React siempre. Cero uso de `class`.
- **Server-state vs Client-state**: lo del servidor → React Query; lo del cliente → Zustand o local.
- **Tipado estricto**: `strict: true` en `tsconfig.json`. Prohibido `any` (usar `unknown` y narrow).
- **Accesibilidad (A11Y)**: usar componentes nativos cuando se pueda (`<button>` antes que `<div onClick>`), `aria-label`, foco visible, contraste WCAG AA.
- **Mobile First**: empezar el CSS por móvil, agregar breakpoints (`sm:`, `md:`, `lg:`) para pantallas mayores.
- **No premature optimization**: empezar simple, optimizar cuando haya métricas (React Profiler, Lighthouse).

---

## 6. Arquitectura del proyecto

### Estructura de carpetas (Feature-Based)

```
src/
├── app/                          # Configuración global de la aplicación
│   ├── App.tsx                   # Provider de routing + react-query + theme
│   ├── providers/                # Wrappers globales (QueryClient, Theme, Auth)
│   └── router.tsx                # Definición central de rutas
│
├── pages/                        # Páginas (rutas) — finas, delegan a features
│   ├── auth/
│   │   ├── LoginPage.tsx
│   │   └── RegisterPage.tsx
│   ├── projects/
│   │   ├── ProjectsListPage.tsx
│   │   └── ProjectDetailPage.tsx
│   ├── executions/
│   │   ├── ExecutionDetailPage.tsx
│   │   └── ExecutionsHistoryPage.tsx
│   ├── settings/
│   │   └── CredentialsPage.tsx
│   ├── NotFoundPage.tsx
│   └── UnauthorizedPage.tsx
│
├── features/                     # ★ corazón: una carpeta por dominio funcional
│   ├── auth/
│   │   ├── components/           # LoginForm, RegisterForm, AuthGuard
│   │   ├── hooks/                # useLogin, useLogout, useCurrentUser
│   │   ├── services/             # auth.service.ts (axios calls)
│   │   ├── schemas/              # loginSchema, registerSchema (Zod)
│   │   ├── types/                # User, TokenResponse
│   │   └── index.ts              # barrel export del feature
│   ├── projects/
│   ├── executions/
│   ├── jira-hus/
│   ├── files/
│   └── credentials/
│
├── components/                   # Componentes 100% genéricos y reutilizables
│   ├── ui/                       # shadcn/ui (Button, Card, Dialog, Input...)
│   ├── layout/                   # Header, Sidebar, Footer, Container
│   ├── feedback/                 # Spinner, EmptyState, ErrorBoundary
│   └── common/                   # DataTable, StatusBadge, FileDropzone
│
├── layouts/                      # Composiciones de layout reusables
│   ├── AppLayout.tsx             # Sidebar + Header + <Outlet />
│   ├── AuthLayout.tsx            # Pantalla centrada para login/register
│   └── BlankLayout.tsx           # Sin chrome (ej. para vistas embed)
│
├── routes/                       # Helpers de routing
│   ├── ProtectedRoute.tsx        # Verifica auth + rol
│   ├── RoleGate.tsx              # Render condicional por rol
│   └── routes.constants.ts       # Paths como constantes (/login, /projects)
│
├── services/                     # Capa de comunicación HTTP
│   ├── api/
│   │   ├── client.ts             # axios.create + interceptores
│   │   ├── endpoints.ts          # rutas tipadas como constantes
│   │   └── error-handler.ts      # mapeo de errores HTTP a mensajes UI
│   └── websocket/
│       └── execution-ws.ts       # cliente WS reusable
│
├── hooks/                        # Hooks genéricos (no atados a features)
│   ├── useDebounce.ts
│   ├── useMediaQuery.ts
│   ├── useLocalStorage.ts
│   └── useClipboard.ts
│
├── store/                        # Estado global con Zustand
│   ├── auth.store.ts             # token, user, rol
│   ├── ui.store.ts               # sidebar abierto, theme, modal global
│   └── index.ts
│
├── types/                        # Tipos compartidos por toda la app
│   ├── api.ts                    # ApiError, Paginated<T>
│   ├── domain.ts                 # tipos de negocio compartidos
│   └── global.d.ts               # tipos globales (env, módulos)
│
├── utils/                        # Funciones puras y reutilizables
│   ├── cn.ts                     # tailwind-merge + clsx
│   ├── format-date.ts
│   ├── format-bytes.ts
│   ├── jwt.ts                    # decode JWT (sin verificación, solo lectura)
│   └── download-file.ts          # helper para Blob → descarga
│
├── constants/                    # Constantes globales
│   ├── app.constants.ts          # APP_NAME, VERSION
│   ├── routes.ts                 # paths (re-exportado desde routes/)
│   └── status.ts                 # ExecutionStatus enum, colores, labels
│
├── assets/                       # Estáticos
│   ├── images/
│   ├── logos/
│   └── fonts/
│
├── styles/                       # Tailwind config + global CSS
│   └── globals.css               # @tailwind base/components/utilities + reset
│
├── main.tsx                      # entry point
└── vite-env.d.ts                 # tipos de Vite
```

### Regla de oro de organización

> **Si lo usa más de un feature** → vive en `components/`, `hooks/`, `utils/`.
> **Si lo usa solo un feature** → vive dentro de ese `features/<X>/`.

Esto evita el monolito en `components/` y mantiene los features cohesivos.

### Barrel exports

Cada `feature/` y carpeta de componentes exporta su API pública vía `index.ts`:

```ts
// features/auth/index.ts
export { LoginForm } from "./components/LoginForm";
export { useLogin, useCurrentUser } from "./hooks";
export type { User } from "./types";
```

---

## 7. Convenciones de código y nomenclatura

| Tipo | Convención | Ejemplo |
|---|---|---|
| **Componente** | PascalCase | `ExecutionPanel.tsx` |
| **Hook** | camelCase con prefijo `use` | `useExecutionStatus.ts` |
| **Service** | kebab-case `.service.ts` | `executions.service.ts` |
| **Schema (Zod)** | camelCase con sufijo `Schema` | `loginSchema` |
| **Type/Interface** | PascalCase, sin prefijo `I` | `User`, `Project`, `ExecutionStatus` |
| **Constante** | UPPER_SNAKE_CASE | `MAX_FILE_SIZE_MB` |
| **Carpeta** | kebab-case | `jira-hus/` |
| **Variable booleana** | prefijo `is`, `has`, `can`, `should` | `isLoading`, `canEdit` |
| **Handler** | prefijo `handle` o `on` | `handleSubmit`, `onClick` |
| **Función de fetching** | verbo + dominio | `fetchProjects`, `createExecution` |

### Imports

Orden y separación visual:

```ts
// 1. React y librerías externas
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

// 2. Imports absolutos del proyecto (alias @/)
import { Button } from "@/components/ui/button";
import { authService } from "@/features/auth/services/auth.service";
import { useAuthStore } from "@/store/auth.store";

// 3. Imports relativos (mismo feature)
import { LoginForm } from "./LoginForm";

// 4. Tipos (al final, con `type`)
import type { LoginRequest } from "@/features/auth/types";
```

Configurar alias `@/*` → `src/*` en `tsconfig.json` y `vite.config.ts`.

### Componentes funcionales

```tsx
type ExecutionCardProps = {
  execution: Execution;
  onSelect?: (id: string) => void;
};

export function ExecutionCard({ execution, onSelect }: ExecutionCardProps) {
  // ...
}
```

- Funciones nombradas (mejor para stack traces que arrow functions exportadas).
- Props tipadas con `type`, no `interface` (más simple, sin extensión accidental).
- Sin `React.FC` (deprecated en patrones modernos).

---

## 8. Consumo de API

### Cliente Axios centralizado

```ts
// src/services/api/client.ts
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "@/store/auth.store";
import { toast } from "sonner";

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// --- Request: inyecta el JWT en cada llamada ---
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Response: errores globales centralizados ---
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail ?? error.message;

    if (status === 401) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      return Promise.reject(error);
    }

    // Errores transitorios → toast genérico (los específicos los maneja el caller)
    if (status && status >= 500) {
      toast.error("Error del servidor", { description: detail });
    }

    return Promise.reject(error);
  },
);
```

### Tipado de respuestas

Los **DTOs del backend** se replican como tipos TS en `src/features/*/types`:

```ts
// src/features/executions/types/index.ts
export type ExecutionStatus =
  | "pending"
  | "extracting"
  | "generating"
  | "complete"
  | "partial"
  | "failed";

export interface Execution {
  id: string;
  jira_ticket_id: string | null;
  jira_ticket_summary: string | null;
  ai_model: string;
  status: ExecutionStatus;
  endpoints_total: number;
  endpoints_selected: number;
  endpoints_generated: number;
  created_at: string;
  completed_at: string | null;
}
```

> ⚙️ **Tip opcional**: generar estos tipos automáticamente desde el `openapi.json`
> de FastAPI usando [openapi-typescript](https://www.npmjs.com/package/openapi-typescript).

### Services tipados

```ts
// src/features/executions/services/executions.service.ts
import { apiClient } from "@/services/api/client";
import type { Execution, ExecutionStatus } from "../types";

export const executionsService = {
  list: async (projectId: string): Promise<Execution[]> => {
    const { data } = await apiClient.get(`/projects/${projectId}/executions`);
    return data;
  },

  create: async (projectId: string, jiraTicketId?: string): Promise<{ execution_id: string; status: ExecutionStatus }> => {
    const { data } = await apiClient.post("/executions", {
      project_id: projectId,
      jira_ticket_id: jiraTicketId,
    });
    return data;
  },

  uploadCollection: async (executionId: string, collection: File, env?: File) => {
    const formData = new FormData();
    formData.append("collection", collection);
    if (env) formData.append("environment", env);
    const { data } = await apiClient.post(
      `/executions/${executionId}/upload`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return data;
  },

  generate: async (executionId: string) => {
    const { data } = await apiClient.post(`/executions/${executionId}/generate`, {});
    return data;
  },
};
```

### Hooks con React Query

```ts
// src/features/executions/hooks/useExecutions.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { executionsService } from "../services/executions.service";

export const executionsKeys = {
  all: ["executions"] as const,
  byProject: (projectId: string) => [...executionsKeys.all, "project", projectId] as const,
  detail: (id: string) => [...executionsKeys.all, "detail", id] as const,
};

export function useExecutionsByProject(projectId: string) {
  return useQuery({
    queryKey: executionsKeys.byProject(projectId),
    queryFn: () => executionsService.list(projectId),
    enabled: Boolean(projectId),
  });
}

export function useGenerateExecution() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: executionsService.generate,
    onSuccess: (_, executionId) => {
      queryClient.invalidateQueries({ queryKey: executionsKeys.detail(executionId) });
    },
  });
}
```

### Manejo de errores específicos

Cada `useMutation`/`useQuery` maneja sus errores localmente cuando hay UX específica:

```tsx
const generate = useGenerateExecution();

const onGenerate = () => {
  generate.mutate(executionId, {
    onError: (err: AxiosError<{ detail: string }>) => {
      if (err.response?.status === 409) {
        toast.error("Falta extraer endpoints", {
          description: "Sube la colección Postman y ejecuta extract antes de generar.",
        });
      } else {
        toast.error("Error al generar", { description: err.response?.data?.detail });
      }
    },
  });
};
```

### React Query — configuración global

```tsx
// src/app/providers/QueryProvider.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,          // 1 min: evita refetch en cada montaje
      retry: 1,                   // un solo retry automático
      refetchOnWindowFocus: false // evita ruido al cambiar de tab
    },
    mutations: {
      retry: 0,
    },
  },
});

export function QueryProvider({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

---

## 9. Manejo de estado

### Estrategia en 3 capas

```
┌─────────────────────────────────────────────────────────┐
│  Server state   →   React Query                         │
│  (datos del backend, listados, detalle, mutaciones)     │
├─────────────────────────────────────────────────────────┤
│  Global client state   →   Zustand                      │
│  (sesión, user, sidebar, theme — pocas cosas)           │
├─────────────────────────────────────────────────────────┤
│  Local component state   →   useState / useReducer      │
│  (form abierto, hover, tab activo)                      │
└─────────────────────────────────────────────────────────┘
```

**Regla**: si el dato vive en el backend, NUNCA lo dupliques en Zustand.
Solo en React Query. El frontend NO mantiene su propia copia.

### Zustand store de autenticación

```ts
// src/store/auth.store.ts
import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/features/auth/types";

type AuthState = {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      setAuth: (token, user) => set({ token, user, isAuthenticated: true }),
      logout: () => set({ token: null, user: null, isAuthenticated: false }),
    }),
    {
      name: "qa-ai-auth",
      // Solo persistimos token y user — el resto se deriva
      partialize: (state) => ({ token: state.token, user: state.user }),
      // Al rehidratar, re-evaluar isAuthenticated
      onRehydrateStorage: () => (state) => {
        if (state) state.isAuthenticated = Boolean(state.token);
      },
    },
  ),
);
```

### Selectores granulares

Para evitar re-renders innecesarios, usar **selectores específicos**:

```ts
// ❌ MAL: este componente re-renderiza si CUALQUIER campo del store cambia
const { user } = useAuthStore();

// ✅ BIEN: solo re-renderiza si user cambia
const user = useAuthStore((state) => state.user);
```

### Persistencia

- **Token**: persistido en `localStorage` vía Zustand `persist`. Se rehidrata al cargar la app.
- **Preferencias UI** (theme, sidebar abierto): igual con `persist`.
- **Datos del servidor**: nunca persistir manualmente; React Query cachea en memoria.

---

## 10. Roles, permisos y rutas protegidas (RBAC)

### Modelo de roles

```ts
// src/types/domain.ts
export type UserRole = "admin" | "qa";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
}
```

### Matriz de permisos

| Acción | qa | admin |
|---|:---:|:---:|
| Login/logout | ✅ | ✅ |
| Gestionar SUS proyectos | ✅ | ✅ |
| Ver proyectos de otros usuarios | ❌ | ✅ |
| Eliminar proyectos de otros | ❌ | ✅ |
| Configurar credenciales propias | ✅ | ✅ |
| Ver historial global | ❌ | ✅ |

### `ProtectedRoute` — auth gate

```tsx
// src/routes/ProtectedRoute.tsx
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuthStore } from "@/store/auth.store";

export function ProtectedRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <Outlet />;
}
```

### `RoleGate` — render condicional por rol

```tsx
// src/routes/RoleGate.tsx
import { Navigate, Outlet } from "react-router-dom";
import { useAuthStore } from "@/store/auth.store";
import type { UserRole } from "@/types/domain";

type Props = {
  allow: UserRole[];
  redirectTo?: string;
  fallback?: React.ReactNode;
  /**
   * Si está dentro de un <Route>, no se pasa children → renderiza <Outlet />.
   * Si se usa como wrapper inline en un componente, se pasa fallback/children.
   */
  children?: React.ReactNode;
};

export function RoleGate({ allow, redirectTo = "/unauthorized", fallback, children }: Props) {
  const role = useAuthStore((s) => s.user?.role);
  const allowed = role && allow.includes(role);

  if (!allowed) {
    if (fallback !== undefined) return <>{fallback}</>;
    if (children !== undefined) return null;
    return <Navigate to={redirectTo} replace />;
  }
  return children ? <>{children}</> : <Outlet />;
}
```

### Definición del router con guards

```tsx
// src/app/router.tsx
import { createBrowserRouter } from "react-router-dom";
import { AppLayout } from "@/layouts/AppLayout";
import { AuthLayout } from "@/layouts/AuthLayout";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { RoleGate } from "@/routes/RoleGate";
// pages...

export const router = createBrowserRouter([
  {
    element: <AuthLayout />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: "/", element: <Navigate to="/projects" replace /> },
          { path: "/projects", element: <ProjectsListPage /> },
          { path: "/projects/:id", element: <ProjectDetailPage /> },
          { path: "/executions/:id", element: <ExecutionDetailPage /> },
          { path: "/settings/credentials", element: <CredentialsPage /> },

          // Solo admin
          {
            element: <RoleGate allow={["admin"]} />,
            children: [
              { path: "/admin/users", element: <UsersAdminPage /> },
              { path: "/admin/history", element: <GlobalHistoryPage /> },
            ],
          },
        ],
      },
    ],
  },
  { path: "/unauthorized", element: <UnauthorizedPage /> },
  { path: "*", element: <NotFoundPage /> },
]);
```

### Render condicional inline

```tsx
import { RoleGate } from "@/routes/RoleGate";

export function ProjectCard({ project }: Props) {
  return (
    <Card>
      <CardHeader>{project.name}</CardHeader>
      <CardActions>
        <Button>Ver</Button>
        <RoleGate allow={["admin"]} fallback={null}>
          <Button variant="destructive" onClick={onDelete}>
            Eliminar (admin)
          </Button>
        </RoleGate>
      </CardActions>
    </Card>
  );
}
```

### Hook helper

```ts
// src/features/auth/hooks/useCurrentRole.ts
import { useAuthStore } from "@/store/auth.store";
import type { UserRole } from "@/types/domain";

export function useCurrentRole(): UserRole | null {
  return useAuthStore((s) => s.user?.role ?? null);
}

export function useHasRole(...roles: UserRole[]): boolean {
  const role = useCurrentRole();
  return role !== null && roles.includes(role);
}
```

---

## 11. Integración con WebSocket

El backend expone `ws://.../ws/executions/{id}?token=<JWT>` que emite eventos
durante la generación. El frontend debe conectarse cuando el usuario inicia un
`generate` y mostrar el progreso en tiempo real.

### Cliente WebSocket reusable

```ts
// src/services/websocket/execution-ws.ts
type ExecutionEvent =
  | { type: "started"; total: number }
  | { type: "file_ready"; current: number; total: number; endpoint: string; files: string[] }
  | { type: "error"; current: number; endpoint: string; message: string }
  | { type: "complete"; status: "complete" | "partial" | "failed"; total: number; generated: number }
  | { type: "fatal_error"; message: string }
  | { type: "ping" | "pong" };

export function createExecutionWebSocket(
  executionId: string,
  token: string,
  onEvent: (event: ExecutionEvent) => void,
): { close: () => void } {
  const wsBase = (import.meta.env.VITE_WS_URL ?? "ws://localhost:8000");
  const ws = new WebSocket(`${wsBase}/ws/executions/${executionId}?token=${token}`);

  const pinger = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) ws.send("ping");
  }, 25_000);

  ws.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data) as ExecutionEvent;
      onEvent(event);
    } catch {/* ignora frames no-JSON */}
  };

  ws.onclose = () => clearInterval(pinger);

  return {
    close: () => {
      clearInterval(pinger);
      ws.close();
    },
  };
}
```

### Hook que integra WS con React Query

```ts
// src/features/executions/hooks/useExecutionProgress.ts
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/auth.store";
import { createExecutionWebSocket } from "@/services/websocket/execution-ws";
import { executionsKeys } from "./useExecutions";

export function useExecutionProgress(executionId: string | undefined) {
  const token = useAuthStore((s) => s.token);
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState({ current: 0, total: 0, isDone: false });

  useEffect(() => {
    if (!executionId || !token) return;

    const { close } = createExecutionWebSocket(executionId, token, (event) => {
      switch (event.type) {
        case "started":
          setProgress({ current: 0, total: event.total, isDone: false });
          break;
        case "file_ready":
          setProgress({ current: event.current, total: event.total, isDone: false });
          // Refrescar lista de archivos
          queryClient.invalidateQueries({
            queryKey: [...executionsKeys.detail(executionId), "files"],
          });
          break;
        case "complete":
          setProgress((p) => ({ ...p, isDone: true }));
          queryClient.invalidateQueries({
            queryKey: executionsKeys.detail(executionId),
          });
          break;
        case "fatal_error":
          // toast + invalidate
          break;
      }
    });

    return close;
  }, [executionId, token, queryClient]);

  return progress;
}
```

---

## 12. Diseño UI/UX y accesibilidad

### Sistema de diseño con Tailwind

- **Tokens semánticos** vía CSS variables (`--color-primary`, `--color-destructive`)
  configurados en `tailwind.config.ts`. Permite tema claro/oscuro sin esfuerzo.
- **shadcn/ui** ya respeta esas variables — los componentes heredan el tema.
- **Tipografía consistente**: 1 sola fuente (ej. Inter), 3-4 tamaños (`text-sm`, `text-base`, `text-lg`, `text-xl`).
- **Espaciado**: usar la escala de Tailwind (`gap-2`, `gap-4`, `gap-8`), no valores arbitrarios.

### Estados que TODOS los componentes de datos deben manejar

```
loading   →   <Skeleton />
empty     →   <EmptyState title="..." description="..." cta={...} />
error     →   <ErrorState onRetry={refetch} />
success   →   render real
```

Estos cuatro estados son no negociables — si un componente solo maneja "success",
está incompleto.

### Accesibilidad (A11Y)

- Usar componentes **semánticos**: `<button>`, `<nav>`, `<main>`, `<header>`, `<form>`.
- Todo input requiere `<label htmlFor>` o `aria-label`.
- Foco siempre visible (no usar `outline: none` sin alternativa).
- Modales bloquean el foco fuera (Radix lo hace nativo).
- Contraste mínimo **WCAG AA** (4.5:1 para texto normal).
- `aria-live="polite"` para anuncios dinámicos (ej. progreso de generación).

### Responsive Mobile First

```tsx
// ❌ Mal: pensado en desktop primero
<div className="flex gap-8 md:flex-col">

// ✅ Bien: mobile first, escala hacia arriba
<div className="flex flex-col gap-4 md:flex-row md:gap-8">
```

Breakpoints estándar de Tailwind:
- `sm:` 640px (móvil horizontal)
- `md:` 768px (tablet)
- `lg:` 1024px (laptop)
- `xl:` 1280px (desktop)
- `2xl:` 1536px (pantalla grande)

### Animaciones con Framer Motion

Usar para:
- Transiciones de página (`<AnimatePresence>` con `mode="wait"`)
- Listas con stagger (delays incrementales)
- Mostrar/ocultar paneles laterales
- Feedback visual de drag-and-drop

No usar para microinteracciones triviales — Tailwind `transition-colors duration-200` basta.

### Notificaciones con Sonner

Reglas:
- **Toast de error** → siempre incluir descripción accionable, no solo "Error".
- **Toast de éxito** → corto, 3 segundos.
- **Toast persistente** → solo para operaciones largas con cancelación posible.
- Posición: `top-right` en desktop, `top-center` en móvil.

---

## 13. Setup inicial del proyecto

### Crear el proyecto

```bash
pnpm create vite@latest qa-ai-frontend -- --template react-ts
cd qa-ai-frontend
pnpm install
```

### Instalar dependencias

```bash
# Core
pnpm add axios @tanstack/react-query react-router-dom zustand

# Forms
pnpm add react-hook-form zod @hookform/resolvers

# UI
pnpm add lucide-react sonner framer-motion clsx tailwind-merge

# Data viz (cuando aplique)
pnpm add recharts date-fns

# Tailwind
pnpm add -D tailwindcss postcss autoprefixer
pnpm dlx tailwindcss init -p

# shadcn/ui
pnpm dlx shadcn@latest init
pnpm dlx shadcn@latest add button card input dialog toast skeleton

# Dev tools
pnpm add -D @tanstack/react-query-devtools
pnpm add -D eslint @typescript-eslint/eslint-plugin @typescript-eslint/parser
pnpm add -D prettier prettier-plugin-tailwindcss
pnpm add -D vitest @testing-library/react @testing-library/jest-dom
pnpm add -D husky lint-staged
```

### Configurar alias `@/*`

**`tsconfig.json`** (paths):
```json
{
  "compilerOptions": {
    "baseUrl": ".",
    "paths": {
      "@/*": ["src/*"]
    },
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  }
}
```

**`vite.config.ts`**:
```ts
import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
});
```

### Variables de entorno

Crear `.env.local`:
```
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000
```

Tipos en `src/vite-env.d.ts`:
```ts
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string;
  readonly VITE_WS_URL: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

### Scripts de package.json

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext .ts,.tsx",
    "lint:fix": "eslint . --ext .ts,.tsx --fix",
    "format": "prettier --write \"src/**/*.{ts,tsx,css,md}\"",
    "test": "vitest",
    "test:ui": "vitest --ui",
    "prepare": "husky install"
  }
}
```

---

## 14. Flujos funcionales que el frontend debe soportar

El frontend debe implementar las siguientes **journeys** de usuario, ordenadas
por prioridad:

### Flujo 1 — Onboarding y autenticación
```
/login → ingresa credenciales → token guardado → redirect a /projects
/register → crea cuenta → auto-login → redirect a /settings/credentials
```

### Flujo 2 — Configuración inicial (una vez)
```
/settings/credentials → guarda Jira server/email/token + Gemini API key
```

### Flujo 3 — Catálogo de HUs
```
/jira → click "Sincronizar con Jira" → POST /jira/tickets
→ GET /jira/tickets → tabla con descripción completa, sprint, assignee
→ click una HU → vista de detalle con criterios estructurados
```

### Flujo 4 — Pipeline de generación (★ flujo principal)
```
/projects/:id → "Nueva ejecución"
  ├─ Paso 1: subir colección Postman (drag-and-drop)
  ├─ Paso 2: confirmar endpoints extraídos (checkboxes)
  ├─ Paso 3: elegir HU de Jira (autocomplete del catálogo)
  ├─ Paso 4: revisar criterios cruzados por la IA
  ├─ Paso 5: "Generar tests" → conecta WS y muestra progreso
  └─ Paso 6: ver archivos generados + descarga ZIP
```

Componente sugerido: `<Stepper>` de shadcn con indicador de progreso por estado.

### Flujo 5 — Edición manual de archivos
```
/executions/:id/files/:name → editor (Monaco o textarea con sintaxis)
→ "Guardar" → PATCH /files/:name → toast de confirmación
```

### Flujo 6 — Vista admin (solo rol admin)
```
/admin/history → tabla con todas las ejecuciones del sistema, filtros por usuario/estado
/admin/users → listado de usuarios (futuro)
```

### Flujo 7 — Manejo de errores comunes
- Sesión expirada → modal "Tu sesión expiró" → redirige a login.
- Backend caído → banner persistente "Servidor no disponible" + retry.
- Credenciales Jira faltantes (424) → CTA "Configurar Jira" → /settings/credentials.

---

## 15. Checklist de calidad antes de cada PR

Antes de marcar un PR como "ready for review":

### Funcional
- [ ] El feature funciona en Chrome y Safari.
- [ ] Responsive verificado en breakpoint móvil (375px).
- [ ] Estados loading / empty / error / success implementados.
- [ ] No deja `console.log` ni código comentado.

### Tipado
- [ ] Cero `any` (usar `unknown` + narrowing si hace falta).
- [ ] `pnpm tsc --noEmit` pasa sin warnings.
- [ ] Tipos de DTOs alineados con el backend.

### Calidad
- [ ] `pnpm lint` sin errores.
- [ ] `pnpm format` aplicado.
- [ ] Componente sin más de 200 líneas (si no, dividir).
- [ ] Sin hardcoded strings de copy → mover a `constants/` o `i18n` (futuro).

### Accesibilidad
- [ ] Inputs con label.
- [ ] Botones con `aria-label` si solo tienen icono.
- [ ] Foco visible en interacción por teclado.
- [ ] Contraste verificado (DevTools → Lighthouse).

### React Query
- [ ] `queryKey` consistente y tipado.
- [ ] `invalidateQueries` después de cada mutación que muta el cache.
- [ ] `enabled` correctamente configurado para queries dependientes.

### Seguridad
- [ ] El JWT solo se envía vía Axios interceptor (nunca en URL).
- [ ] Inputs de usuario se sanitizan antes de renderizar como HTML.
- [ ] Componentes que muestran datos sensibles verifican el rol.

### Tests
- [ ] Componente con lógica de negocio tiene al menos un test de comportamiento.
- [ ] Hook custom complejo tiene un test que cubre el happy path + error.

---

## Apéndice — Referencias rápidas

### Variables de entorno esperadas

| Variable | Valor local | Valor producción |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | `https://api.qa-ai-assistant.app` |
| `VITE_WS_URL` | `ws://localhost:8000` | `wss://api.qa-ai-assistant.app` |

### Colección Postman de referencia

Hay una colección completa para verificar manualmente el backend en
`postman/qa-ai-assistant.postman_collection.json` con 44 requests organizados,
scripts que auto-guardan variables y documentación inline. Importarla es la forma
más rápida de explorar todos los contratos antes de tipar los DTOs.

### Documentos relacionados

- `postman/README.md` — guía de la colección Postman.
- `GCP_SETUP.md` — despliegue en GCP (backend).
- Swagger UI: `http://localhost:8000/docs` (autogenerado por FastAPI).

---

> **Mantenimiento de este documento**: cualquier decisión arquitectónica nueva
> (cambio de librería, nueva convención, nuevo flujo) debe reflejarse aquí en
> el mismo PR. Un `context.md` desactualizado es peor que ninguno.
