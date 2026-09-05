import type { UseCase } from '../use-case.js';
import type { MachineProductsPort, PriceWriterPort } from '../../ports/nayax.ports.js';
import type { Actor, AuditLogPort, CachePort, ClockPort, LoggerPort } from '../../ports/support.ports.js';
import { machineId as toMachineId, machineProductId as toMachineProductId } from '../../../domain/shared/ids.js';
import { Money } from '../../../domain/shared/money.js';
import { ForbiddenError, NotFoundError, WritesDisabledError } from '../../../domain/shared/errors.js';
import { PriceChangePolicy, type PriceChange } from '../../../domain/product/price-change-policy.js';
import type { PriceKind } from '../../../domain/product/pricing.js';
import { machineProductsCacheKey } from './get-machine-products.use-case.js';

export interface UpdateProductPriceInput {
  readonly machineId: number;
  readonly machineProductId: string;
  /** Precios nuevos en euros. Solo hace falta indicar los que cambian. */
  readonly prices: Partial<Record<PriceKind, number>>;
  /** Si es true, calcula y audita el cambio pero NO lo aplica. */
  readonly dryRun: boolean;
  /** Necesario para cambios que superen el limite de variacion. */
  readonly confirmLargeChange?: boolean;
  readonly actor: Actor;
}

export interface UpdateProductPriceOutput {
  readonly applied: boolean;
  readonly dryRun: boolean;
  readonly productName: string;
  readonly changes: ReadonlyArray<{
    kind: PriceKind;
    previous: number | null;
    next: number;
    variationPercent: number | null;
  }>;
}

export interface UpdateProductPriceConfig {
  readonly writesEnabled: boolean;
  readonly maxPriceVariation: number;
}

/**
 * Cambia uno o varios precios de un producto en una maquina.
 *
 * Este es el caso de uso con efectos reales sobre el mundo fisico: una maquina
 * pasara a cobrar otra cantidad. Por eso concentra las salvaguardas:
 *   1. Permisos (un viewer no escribe).
 *   2. Interruptor global de escrituras.
 *   3. Politica de variacion maxima.
 *   4. Modo dry-run.
 *   5. Auditoria de todo, incluidos los dry-run.
 */
export class UpdateProductPrice
  implements UseCase<UpdateProductPriceInput, UpdateProductPriceOutput>
{
  constructor(
    private readonly products: MachineProductsPort,
    private readonly writer: PriceWriterPort,
    private readonly audit: AuditLogPort,
    private readonly cache: CachePort,
    private readonly clock: ClockPort,
    private readonly logger: LoggerPort,
    private readonly config: UpdateProductPriceConfig,
  ) {}

  async execute(input: UpdateProductPriceInput): Promise<UpdateProductPriceOutput> {
    this.assertCanWrite(input.actor, input.dryRun);

    const machine = toMachineId(input.machineId);
    const productId = toMachineProductId(input.machineProductId);

    const product = await this.products.getById(machine, productId);
    if (!product) {
      throw new NotFoundError('producto de maquina', input.machineProductId);
    }

    const policy = new PriceChangePolicy({
      maxVariation: this.config.maxPriceVariation,
      confirmedLargeChange: input.confirmLargeChange === true,
    });

    const requests = Object.entries(input.prices).map(([kind, value]) => ({
      kind: kind as PriceKind,
      newPrice: Money.fromDecimal(value as number),
    }));

    const changes = policy.evaluate(product, requests);

    if (!input.dryRun && PriceChangePolicy.isNoop(changes)) {
      this.logger.info({ machine, productId }, 'Cambio de precio sin efecto, se omite');
      return this.toOutput(false, input.dryRun, product.name, changes);
    }

    if (!input.dryRun) {
      await this.writer.updatePrices(machine, productId, input.prices);
      await this.cache.invalidatePrefix(machineProductsCacheKey(machine));
    }

    await this.audit.record({
      at: this.clock.now().toISOString(),
      actor: input.actor,
      action: 'product.price.update',
      target: {
        machineId: input.machineId,
        machineProductId: input.machineProductId,
        productName: product.name,
      },
      before: product.pricing.toDecimals(),
      after: { ...product.pricing.toDecimals(), ...input.prices },
      dryRun: input.dryRun,
    });

    return this.toOutput(!input.dryRun, input.dryRun, product.name, changes);
  }

  private assertCanWrite(actor: Actor, dryRun: boolean): void {
    if (actor.role === 'viewer') {
      throw new ForbiddenError('El rol "viewer" no puede modificar precios.');
    }
    if (!dryRun && !this.config.writesEnabled) {
      throw new WritesDisabledError();
    }
  }

  private toOutput(
    applied: boolean,
    dryRun: boolean,
    productName: string,
    changes: readonly PriceChange[],
  ): UpdateProductPriceOutput {
    return {
      applied,
      dryRun,
      productName,
      changes: changes.map((change) => ({
        kind: change.kind,
        previous: change.previous?.toDecimal() ?? null,
        next: change.next.toDecimal(),
        variationPercent:
          change.variation === null || !Number.isFinite(change.variation)
            ? null
            : Number((change.variation * 100).toFixed(2)),
      })),
    };
  }
}
