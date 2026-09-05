/** Puertos de apoyo: infraestructura generica, no Nayax. */

export interface ClockPort {
  now(): Date;
  /** Fecha de hoy en formato YYYY-MM-DD. */
  today(): string;
}

export interface CachePort {
  get<T>(key: string): Promise<T | null>;
  set<T>(key: string, value: T, ttlSeconds?: number): Promise<void>;
  /** Invalida todas las claves que empiecen por el prefijo dado. */
  invalidatePrefix(prefix: string): Promise<void>;
}

export interface LoggerPort {
  debug(obj: object, msg?: string): void;
  info(obj: object, msg?: string): void;
  warn(obj: object, msg?: string): void;
  error(obj: object, msg?: string): void;
}

/** Quien ejecuta la accion. Lo necesitamos para auditar y para permisos. */
export interface Actor {
  readonly id: string;
  readonly role: 'viewer' | 'operator' | 'agent';
  /** Canal desde el que llega: nos interesa distinguir humano de agente. */
  readonly channel: 'http' | 'mcp';
}

export interface AuditEntry {
  readonly at: string;
  readonly actor: Actor;
  readonly action: string;
  readonly target: Record<string, unknown>;
  readonly before: Record<string, unknown> | null;
  readonly after: Record<string, unknown> | null;
  readonly dryRun: boolean;
}

export interface AuditLogPort {
  record(entry: AuditEntry): Promise<void>;
  list(limit: number): Promise<AuditEntry[]>;
}
