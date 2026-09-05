import { IntegrationError } from '../../domain/shared/errors.js';
import type { LoggerPort } from '../../application/ports/support.ports.js';

export interface NayaxHttpClientOptions {
  readonly baseUrl: string;
  readonly apiPrefix: string;
  readonly token: string;
  readonly timeoutMs: number;
  readonly maxRetries: number;
}

export interface RequestOptions {
  readonly method: 'GET' | 'POST' | 'PUT' | 'DELETE';
  readonly path: string;
  readonly body?: unknown;
  readonly query?: Record<string, string | number | undefined>;
}

const RETRIABLE_STATUS = new Set([408, 429, 500, 502, 503, 504]);

/**
 * Cliente HTTP de bajo nivel contra Lynx.
 *
 * Unica responsabilidad: hablar HTTP con Nayax. No sabe de dominio, no mapea
 * entidades, no decide reglas. Solo transporte, autenticacion, reintentos y
 * traduccion de fallos a IntegrationError.
 *
 * Los reintentos son solo para GET y para errores transitorios. Reintentar un
 * PUT de precio a ciegas podria aplicar un cambio dos veces.
 */
export class NayaxHttpClient {
  constructor(
    private readonly options: NayaxHttpClientOptions,
    private readonly logger: LoggerPort,
  ) {}

  async request<T>(options: RequestOptions): Promise<T> {
    const url = this.buildUrl(options.path, options.query);
    const isRetriable = options.method === 'GET';
    const attempts = isRetriable ? this.options.maxRetries + 1 : 1;

    let lastError: unknown;

    for (let attempt = 1; attempt <= attempts; attempt++) {
      try {
        return await this.doRequest<T>(url, options, attempt);
      } catch (error) {
        lastError = error;

        const retriable =
          isRetriable &&
          error instanceof IntegrationError &&
          (error.upstreamStatus === undefined || RETRIABLE_STATUS.has(error.upstreamStatus));

        if (!retriable || attempt === attempts) break;

        const backoffMs = 250 * 2 ** (attempt - 1);
        this.logger.warn({ url, attempt, backoffMs }, 'Reintentando llamada a Nayax');
        await sleep(backoffMs);
      }
    }

    throw lastError;
  }

  private async doRequest<T>(url: string, options: RequestOptions, attempt: number): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.options.timeoutMs);
    const startedAt = Date.now();

    try {
      const response = await fetch(url, {
        method: options.method,
        headers: {
          Authorization: `Bearer ${this.options.token}`,
          Accept: 'application/json',
          ...(options.body !== undefined ? { 'Content-Type': 'application/json' } : {}),
        },
        ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
        signal: controller.signal,
      });

      const durationMs = Date.now() - startedAt;
      this.logger.debug(
        { method: options.method, url, status: response.status, durationMs, attempt },
        'Llamada a Nayax',
      );

      const text = await response.text();
      const payload = text ? safeJsonParse(text) : null;

      if (!response.ok) {
        throw new IntegrationError(
          `Nayax respondio ${response.status} en ${options.method} ${options.path}`,
          response.status,
          payload,
        );
      }

      return payload as T;
    } catch (error) {
      if (error instanceof IntegrationError) throw error;

      if (error instanceof Error && error.name === 'AbortError') {
        throw new IntegrationError(
          `Timeout de ${this.options.timeoutMs}ms llamando a Nayax: ${options.method} ${options.path}`,
        );
      }

      throw new IntegrationError(
        `Fallo de red llamando a Nayax: ${error instanceof Error ? error.message : String(error)}`,
      );
    } finally {
      clearTimeout(timer);
    }
  }

  private buildUrl(path: string, query?: Record<string, string | number | undefined>): string {
    const base = this.options.baseUrl.replace(/\/+$/, '');
    const prefix = this.options.apiPrefix.replace(/\/+$/, '');
    const cleanPath = path.startsWith('/') ? path : `/${path}`;
    const url = new URL(`${base}${prefix}${cleanPath}`);

    for (const [key, value] of Object.entries(query ?? {})) {
      if (value !== undefined) url.searchParams.set(key, String(value));
    }

    return url.toString();
  }
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
