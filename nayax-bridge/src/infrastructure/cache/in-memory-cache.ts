import type { CachePort } from '../../application/ports/support.ports.js';

interface Entry {
  value: unknown;
  expiresAt: number;
}

/**
 * Cache en memoria con TTL.
 *
 * Suficiente para una sola instancia. Cuando escales a varias, implementa
 * RedisCache con este mismo puerto y no habra que tocar ningun caso de uso.
 *
 * Nota: guarda referencias a los objetos tal cual, asi que conserva las
 * instancias de clase (Money, Pricing). Una implementacion con Redis tendria
 * que serializar y por tanto necesitaria mappers de ida y vuelta.
 */
export class InMemoryCache implements CachePort {
  private readonly store = new Map<string, Entry>();

  constructor(private readonly defaultTtlSeconds: number) {}

  async get<T>(key: string): Promise<T | null> {
    const entry = this.store.get(key);
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      this.store.delete(key);
      return null;
    }
    return entry.value as T;
  }

  async set<T>(key: string, value: T, ttlSeconds?: number): Promise<void> {
    const ttl = ttlSeconds ?? this.defaultTtlSeconds;
    if (ttl <= 0) return;
    this.store.set(key, { value, expiresAt: Date.now() + ttl * 1000 });
  }

  async invalidatePrefix(prefix: string): Promise<void> {
    for (const key of this.store.keys()) {
      if (key.startsWith(prefix)) {
        this.store.delete(key);
      }
    }
  }

  /** Cache desactivada: util en tests para no arrastrar estado. */
  static disabled(): CachePort {
    return new InMemoryCache(0);
  }
}
