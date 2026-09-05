# nayax-bridge — contexto del proyecto

> Este fichero lo lee Claude Code automáticamente al abrir el proyecto.
> Si cambias una decisión de arquitectura, actualízalo aquí.

## Qué es esto

API puente sobre **Nayax Lynx** para operar máquinas de vending con TPV Nayax.

Es "el cerebro": un único núcleo de casos de uso, consumido por dos puertas de entrada:

- **HTTP** (Fastify) → lo consume la aplicación frontal.
- **MCP** (stdio) → lo consumen agentes de IA.

Ambas puertas llaman a los **mismos** casos de uso. Nunca dupliques lógica entre ellas.

Casos de uso reales: consultar ventas diarias, revisar el mapa de productos de una máquina,
y **cambiar precios** (que afecta a máquinas físicas cobrando dinero real a clientes).

## Regla de oro de la arquitectura

Hexagonal. **Las dependencias apuntan siempre hacia dentro:**

```
interfaces/  →  application/  →  domain/
     ↑                              ↑
infrastructure/ ────────────────────┘
   (implementa los puertos de application/)
```

| Capa | Puede importar de | NUNCA importa de |
|---|---|---|
| `domain/` | solo de `domain/` | nada más. Ni zod, ni fastify, ni Nayax |
| `application/` | `domain/` | `infrastructure/`, `interfaces/` |
| `infrastructure/` | `domain/`, `application/ports` | `interfaces/` |
| `interfaces/` | todo | — |

Si te ves importando `NayaxHttpClient` dentro de un caso de uso, algo va mal:
el caso de uso debe recibir un **puerto** (interfaz) por constructor.

## Estructura

```
src/
  domain/           Reglas de negocio puras. Money, Pricing, PriceChangePolicy.
                    Sin IO, sin red. Testeable en milisegundos.
  application/
    ports/          Interfaces hacia fuera (MachinesPort, PriceWriterPort, CachePort...)
    use-cases/      Una clase = una acción de negocio = un método execute()
  infrastructure/   Implementaciones concretas: cliente Lynx, caché, auditoría, config
  interfaces/
    http/           Fastify: rutas, middlewares. Controladores FINOS.
    mcp/            Servidor MCP: herramientas que envuelven casos de uso.
  shared/           Esquemas Zod y presentadores compartidos por HTTP y MCP
  container.ts      Composition root: el ÚNICO sitio donde se hace `new` de clases concretas
  main.ts           Arranque HTTP
  mcp.ts            Arranque MCP
```

## Comandos

```bash
npm run dev          # servidor HTTP con recarga (puerto 3000)
npm run dev:mcp      # servidor MCP por stdio
npm test             # tests (vitest)
npm run typecheck    # tsc --noEmit
npm run build        # compila a dist/
```

## Convenciones

- **ESM + NodeNext.** Los imports relativos llevan extensión `.js` aunque el fichero sea `.ts`.
  `import { Money } from './money.js'` — sí, es raro, pero es lo correcto aquí.
- **TypeScript estricto.** Nada de `any`. Si algo es desconocido, `unknown` y se estrecha.
- **Un caso de uso = un método público `execute`.** Si necesitas un segundo método público,
  es que hacen falta dos casos de uso.
- **Los errores del dominio son clases** de `domain/shared/errors.ts`, con un `code`.
  El adaptador HTTP los traduce a status; el MCP los devuelve como texto para el agente.
  Un error crudo de Nayax nunca debe llegar al cliente.
- **Dinero siempre con `Money`**, nunca `number` suelto. Se guarda en céntimos.
- **Ids con tipos nominales** (`machineId(5001)`), para no confundir un machineId con un
  machineProductId. Ambos son números y TypeScript no avisaría sin esto.
- **Esquemas Zod en `shared/schemas.ts`**, compartidos entre HTTP y MCP. Definir una vez.
- **Comentarios en el código: en español**, explicando el *por qué*, no el *qué*.

## Salvaguardas — NO las quites

Este proyecto toca máquinas reales que cobran dinero. Antes de cambiar algo aquí, pregunta:

1. **`dryRun` por defecto es `true`** en escrituras, tanto en HTTP como en MCP.
   Aplicar de verdad requiere pedirlo explícitamente.
2. **`PriceChangePolicy`** bloquea cambios que superen `MAX_PRICE_CHANGE_RATIO` (30% por
   defecto) salvo confirmación explícita.
3. **Auditoría obligatoria** de toda escritura, incluidas las simulaciones, en
   `data/audit.log.jsonl`. Quién, qué, antes → después, cuándo, desde qué canal.
4. **Roles**: `viewer` no escribe. `operator` (humano) y `agent` (IA) sí.
5. **`WRITES_ENABLED=false`** deja toda la API en solo lectura.
6. **El token de Nayax no sale nunca del servidor.** El frontend y los agentes usan
   API keys propias (`x-api-key`), revocables sin tocar la integración.

## Estado actual y qué falta

**Hecho y probado:**
- Dominio completo con tests (18 en verde).
- Casos de uso: listar máquinas, productos de máquina, resumen de ventas, ventas por
  máquina, cambio de precio individual y en lote.
- Servidor HTTP con auth, validación y manejo de errores.
- Servidor MCP con 7 herramientas (5 de lectura, 2 de escritura).

**Pendiente / a verificar contra Nayax real:**
- ⚠️ **Los endpoints de `infrastructure/nayax/` están escritos desde la documentación,
  no probados contra una cuenta real.** Antes de dar nada por bueno, verifica contra QA
  (`qa-lynx.nayax.com`).
- ⚠️ **`nayax-sales.adapter.ts` es el más incierto.** Lynx no expone un "dame las ventas"
  limpio: hay que pedir datos de widgets con `screenTypeId` / `widgetTypeId`, y esos ids
  dependen de tu cuenta. El parseo está aislado en métodos privados justo para eso.
- Ingesta en tiempo real vía Amazon SQS (fase 3 del plan).
- Alertas de stock bajo y máquina caída.
- Persistencia real (ahora la auditoría va a fichero JSONL y la caché es en memoria).

## Conector MCP de Nayax (documentación)

El proyecto tiene configurado en `.mcp.json` el servidor MCP de documentación de Nayax.
**Úsalo siempre que toques `infrastructure/nayax/`**: contiene la referencia real de
endpoints, nombres de campos y tipos. No inventes nombres de campos de Lynx de memoria.

Ese conector **solo lee documentación**; no accede a la cuenta ni a las máquinas.
La conexión operativa la hace este proyecto con el token de Lynx.

## Configuración

Copia `.env.example` a `.env` y rellena. Lo mínimo para arrancar: `NAYAX_TOKEN`.
La config se valida con Zod al arrancar: si falta algo, la app no arranca (a propósito).

Empieza siempre apuntando a **QA** (`NAYAX_BASE_URL=https://qa-lynx.nayax.com`).
Producción es `https://lynx.nayax.com`.

## Vocabulario: nuestros nombres vs los de Nayax

Nayax maneja cinco precios por producto. En el dominio usamos nombres cortos;
el mapeo vive **solo** en `infrastructure/nayax/nayax.mappers.ts`:

| Nuestro | Nayax | Qué es |
|---|---|---|
| `cash` | `CashPrice` | Efectivo |
| `card` | `CreditCardPrice` | Tarjeta ← el relevante en nuestras máquinas |
| `prepaid` | `PrePaidCardPrice` | Monedero / prepago |
| `machine` | `MachinePrice` | El grabado en la propia máquina |
| `retail` | `RetailPrice` | PVP de referencia |

Si Nayax renombra un campo, se toca ese fichero y nada más.
