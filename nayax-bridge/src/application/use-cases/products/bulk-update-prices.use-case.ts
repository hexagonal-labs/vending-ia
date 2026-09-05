import type { UseCase } from '../use-case.js';
import type { Actor } from '../../ports/support.ports.js';
import type { PriceKind } from '../../../domain/product/pricing.js';
import { DomainError } from '../../../domain/shared/errors.js';
import type {
  UpdateProductPrice,
  UpdateProductPriceOutput,
} from './update-product-price.use-case.js';

export interface BulkPriceItem {
  readonly machineId: number;
  readonly machineProductId: string;
  readonly prices: Partial<Record<PriceKind, number>>;
}

export interface BulkUpdatePricesInput {
  readonly items: readonly BulkPriceItem[];
  readonly dryRun: boolean;
  readonly confirmLargeChange?: boolean;
  readonly actor: Actor;
}

export interface BulkUpdateResultItem {
  readonly machineId: number;
  readonly machineProductId: string;
  readonly ok: boolean;
  readonly result?: UpdateProductPriceOutput;
  readonly error?: { code: string; message: string };
}

export interface BulkUpdatePricesOutput {
  readonly total: number;
  readonly succeeded: number;
  readonly failed: number;
  readonly results: readonly BulkUpdateResultItem[];
}

/**
 * Cambia precios en lote reutilizando el caso de uso individual.
 *
 * Decision de diseno: NO se aborta todo el lote al primer fallo. En vending
 * interesa mas que se apliquen los 19 cambios buenos y saber cual fallo, que
 * quedarse a medias sin saber donde. Cada item se reporta por separado.
 */
export class BulkUpdatePrices implements UseCase<BulkUpdatePricesInput, BulkUpdatePricesOutput> {
  constructor(private readonly updateOne: UpdateProductPrice) {}

  async execute(input: BulkUpdatePricesInput): Promise<BulkUpdatePricesOutput> {
    const results: BulkUpdateResultItem[] = [];

    for (const item of input.items) {
      try {
        const result = await this.updateOne.execute({
          machineId: item.machineId,
          machineProductId: item.machineProductId,
          prices: item.prices,
          dryRun: input.dryRun,
          confirmLargeChange: input.confirmLargeChange,
          actor: input.actor,
        });
        results.push({
          machineId: item.machineId,
          machineProductId: item.machineProductId,
          ok: true,
          result,
        });
      } catch (error) {
        results.push({
          machineId: item.machineId,
          machineProductId: item.machineProductId,
          ok: false,
          error: {
            code: error instanceof DomainError ? error.code : 'UNEXPECTED_ERROR',
            message: error instanceof Error ? error.message : String(error),
          },
        });
      }
    }

    const succeeded = results.filter((r) => r.ok).length;
    return {
      total: results.length,
      succeeded,
      failed: results.length - succeeded,
      results,
    };
  }
}
