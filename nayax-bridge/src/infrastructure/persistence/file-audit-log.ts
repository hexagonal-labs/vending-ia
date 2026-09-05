import { appendFile, mkdir, readFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import type { AuditEntry, AuditLogPort } from '../../application/ports/support.ports.js';

/**
 * Auditoria en fichero JSONL (una entrada JSON por linea).
 *
 * Deliberadamente simple para empezar: append-only, legible con `tail -f`, sin
 * dependencias. Cuando quieras consultas serias, implementa PostgresAuditLog
 * con este mismo puerto.
 *
 * Auditar no es opcional aqui: un agente de IA puede cambiar precios reales y
 * hay que poder responder a "quien subio esto y cuando".
 */
export class FileAuditLog implements AuditLogPort {
  constructor(private readonly filePath: string) {}

  async record(entry: AuditEntry): Promise<void> {
    await mkdir(dirname(this.filePath), { recursive: true });
    await appendFile(this.filePath, `${JSON.stringify(entry)}\n`, 'utf8');
  }

  async list(limit: number): Promise<AuditEntry[]> {
    try {
      const content = await readFile(this.filePath, 'utf8');
      const lines = content.split('\n').filter(Boolean);
      return lines
        .slice(-limit)
        .reverse()
        .map((line) => JSON.parse(line) as AuditEntry);
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === 'ENOENT') return [];
      throw error;
    }
  }
}

/** Version en memoria para tests. */
export class InMemoryAuditLog implements AuditLogPort {
  readonly entries: AuditEntry[] = [];

  async record(entry: AuditEntry): Promise<void> {
    this.entries.push(entry);
  }

  async list(limit: number): Promise<AuditEntry[]> {
    return this.entries.slice(-limit).reverse();
  }
}
