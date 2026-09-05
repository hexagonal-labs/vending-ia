import 'dotenv/config';
import { z } from 'zod';

/**
 * Configuracion validada en el arranque.
 *
 * Si falta algo o esta mal, la app NO arranca. Es preferible a descubrirlo a
 * mitad de una llamada en produccion. Nada de process.env desperdigado por el
 * codigo: se lee aqui y se inyecta.
 */

const apiKeysSchema = z
  .string()
  .transform((raw, ctx) => {
    const entries = raw
      .split(',')
      .map((pair) => pair.trim())
      .filter(Boolean)
      .map((pair) => {
        const [key, role] = pair.split(':');
        return { key: key?.trim() ?? '', role: (role ?? '').trim() };
      });

    if (entries.length === 0) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'API_KEYS no puede estar vacio' });
      return z.NEVER;
    }

    const validRoles = new Set(['viewer', 'operator', 'agent']);
    const map = new Map<string, 'viewer' | 'operator' | 'agent'>();

    for (const entry of entries) {
      if (!entry.key || !validRoles.has(entry.role)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: `Entrada de API_KEYS invalida: "${entry.key}:${entry.role}". Formato: clave:rol`,
        });
        return z.NEVER;
      }
      map.set(entry.key, entry.role as 'viewer' | 'operator' | 'agent');
    }

    return map;
  });

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace']).default('info'),

  HTTP_PORT: z.coerce.number().int().positive().default(3000),
  HTTP_HOST: z.string().default('0.0.0.0'),

  NAYAX_BASE_URL: z.string().url(),
  NAYAX_API_PREFIX: z.string().default('/operational/v1'),
  NAYAX_TOKEN: z.string().min(1, 'Falta el token de Nayax'),
  NAYAX_OPERATOR_ID: z.coerce.number().int().nonnegative().default(0),
  NAYAX_TIMEOUT_MS: z.coerce.number().int().positive().default(15_000),
  NAYAX_MAX_RETRIES: z.coerce.number().int().min(0).max(5).default(2),

  API_KEYS: apiKeysSchema,

  MAX_PRICE_CHANGE_RATIO: z.coerce.number().min(0).max(10).default(0.3),
  WRITES_ENABLED: z
    .string()
    .default('true')
    .transform((value) => value.toLowerCase() === 'true'),
  MCP_WRITES_REQUIRE_DRY_RUN: z
    .string()
    .default('false')
    .transform((value) => value.toLowerCase() === 'true'),

  CACHE_TTL_SECONDS: z.coerce.number().int().nonnegative().default(60),
});

export type AppConfig = z.infer<typeof envSchema>;

let cached: AppConfig | null = null;

export function loadConfig(): AppConfig {
  if (cached) return cached;

  const parsed = envSchema.safeParse(process.env);
  if (!parsed.success) {
    const details = parsed.error.issues
      .map((issue) => `  - ${issue.path.join('.')}: ${issue.message}`)
      .join('\n');
    throw new Error(`Configuracion invalida. Revisa tu .env:\n${details}`);
  }

  cached = parsed.data;
  return cached;
}

/** Solo para tests: permite reinyectar configuracion. */
export function resetConfigCache(): void {
  cached = null;
}
