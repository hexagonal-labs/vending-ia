import { beforeEach, describe, expect, it } from 'vitest';
import { UpdateProductPrice } from '../../../src/application/use-cases/products/update-product-price.use-case.js';
import { InMemoryAuditLog } from '../../../src/infrastructure/persistence/file-audit-log.js';
import { InMemoryCache } from '../../../src/infrastructure/cache/in-memory-cache.js';
import { FixedClock } from '../../../src/infrastructure/system/system-clock.js';
import { Pricing, type PriceKind } from '../../../src/domain/product/pricing.js';
import { machineId, machineProductId } from '../../../src/domain/shared/ids.js';
import { ForbiddenError, PriceChangeTooLargeError, WritesDisabledError } from '../../../src/domain/shared/errors.js';
import type { MachineProduct } from '../../../src/domain/product/machine-product.js';
import type { MachineProductsPort, PriceWriterPort } from '../../../src/application/ports/nayax.ports.js';
import type { Actor, LoggerPort } from '../../../src/application/ports/support.ports.js';

/**
 * Este test demuestra por que merece la pena la arquitectura: se prueba el caso
 * de uso completo, con todas sus reglas de seguridad, sin red, sin Nayax y sin
 * servidor. Corre en milisegundos.
 */

const baseProduct: MachineProduct = {
  machineProductId: machineProductId('101'),
  machineId: machineId(5001),
  nayaxProductId: null,
  catalogProduct: null,
  name: 'Coca-Cola Zero',
  selectionCode: 'A1',
  pricing: Pricing.fromDecimals({ cash: 1.5, card: 1.6 }),
  stock: { par: 10, missing: 0, alertThreshold: 3 },
  lastSaleAt: null,
  slowMover: false,
};

class FakeProductsPort implements MachineProductsPort, PriceWriterPort {
  readonly writes: Array<Partial<Record<PriceKind, number>>> = [];

  async listByMachine(): Promise<MachineProduct[]> {
    return [baseProduct];
  }

  async getById(): Promise<MachineProduct | null> {
    return baseProduct;
  }

  async updatePrices(
    _machineId: unknown,
    _productId: unknown,
    prices: Partial<Record<PriceKind, number>>,
  ): Promise<MachineProduct> {
    this.writes.push(prices);
    return baseProduct;
  }
}

const silentLogger: LoggerPort = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
};

const operator: Actor = { id: 'test-operator', role: 'operator', channel: 'http' };
const viewer: Actor = { id: 'test-viewer', role: 'viewer', channel: 'http' };

describe('UpdateProductPrice', () => {
  let ports: FakeProductsPort;
  let audit: InMemoryAuditLog;

  const build = (writesEnabled = true) => {
    ports = new FakeProductsPort();
    audit = new InMemoryAuditLog();
    return new UpdateProductPrice(
      ports,
      ports,
      audit,
      new InMemoryCache(0),
      new FixedClock(new Date('2026-08-11T10:00:00Z')),
      silentLogger,
      { writesEnabled, maxPriceVariation: 0.3 },
    );
  };

  beforeEach(() => {
    ports = new FakeProductsPort();
    audit = new InMemoryAuditLog();
  });

  it('en dry-run calcula el cambio pero no escribe en Nayax', async () => {
    const useCase = build();

    const result = await useCase.execute({
      machineId: 5001,
      machineProductId: '101',
      prices: { card: 1.8 },
      dryRun: true,
      actor: operator,
    });

    expect(result.applied).toBe(false);
    expect(result.dryRun).toBe(true);
    expect(result.changes[0]!.previous).toBe(1.6);
    expect(result.changes[0]!.next).toBe(1.8);
    expect(ports.writes).toHaveLength(0);
  });

  it('audita tambien las simulaciones', async () => {
    const useCase = build();

    await useCase.execute({
      machineId: 5001,
      machineProductId: '101',
      prices: { card: 1.8 },
      dryRun: true,
      actor: operator,
    });

    expect(audit.entries).toHaveLength(1);
    expect(audit.entries[0]!.dryRun).toBe(true);
    expect(audit.entries[0]!.action).toBe('product.price.update');
  });

  it('aplica el cambio cuando dryRun es false', async () => {
    const useCase = build();

    const result = await useCase.execute({
      machineId: 5001,
      machineProductId: '101',
      prices: { card: 1.8 },
      dryRun: false,
      actor: operator,
    });

    expect(result.applied).toBe(true);
    expect(ports.writes).toEqual([{ card: 1.8 }]);
  });

  it('bloquea a un viewer aunque sea en dry-run', async () => {
    const useCase = build();

    await expect(
      useCase.execute({
        machineId: 5001,
        machineProductId: '101',
        prices: { card: 1.8 },
        dryRun: true,
        actor: viewer,
      }),
    ).rejects.toThrow(ForbiddenError);
  });

  it('respeta el interruptor global de escrituras', async () => {
    const useCase = build(false);

    await expect(
      useCase.execute({
        machineId: 5001,
        machineProductId: '101',
        prices: { card: 1.8 },
        dryRun: false,
        actor: operator,
      }),
    ).rejects.toThrow(WritesDisabledError);
  });

  it('rechaza un cambio desproporcionado sin confirmacion', async () => {
    const useCase = build();

    await expect(
      useCase.execute({
        machineId: 5001,
        machineProductId: '101',
        prices: { card: 5.0 },
        dryRun: false,
        actor: operator,
      }),
    ).rejects.toThrow(PriceChangeTooLargeError);

    expect(ports.writes).toHaveLength(0);
  });

  it('no llama a Nayax si el precio no cambia', async () => {
    const useCase = build();

    const result = await useCase.execute({
      machineId: 5001,
      machineProductId: '101',
      prices: { card: 1.6 },
      dryRun: false,
      actor: operator,
    });

    expect(result.applied).toBe(false);
    expect(ports.writes).toHaveLength(0);
  });
});
