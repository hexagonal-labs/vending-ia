import { Money } from '../shared/money.js';
import { PriceChangeTooLargeError, ValidationError } from '../shared/errors.js';
import type { PriceKind } from './pricing.js';
import type { MachineProduct } from './machine-product.js';

export interface PriceChangeRequest {
  readonly kind: PriceKind;
  readonly newPrice: Money;
}

export interface PriceChange {
  readonly kind: PriceKind;
  readonly previous: Money | null;
  readonly next: Money;
  readonly variation: number | null;
}

export interface PolicyOptions {
  /** Variacion maxima aceptada sin confirmacion, p.ej. 0.30 = 30%. */
  readonly maxVariation: number;
  /** El usuario confirmo explicitamente un cambio grande. */
  readonly confirmedLargeChange: boolean;
}

/**
 * Politica de cambio de precios.
 *
 * Servicio de dominio puro: sin red, sin IO, totalmente testeable. Aqui viven
 * las reglas que protegen de un cambio accidental sobre maquinas reales.
 */
export class PriceChangePolicy {
  constructor(private readonly options: PolicyOptions) {}

  /**
   * Valida los cambios pedidos contra el estado actual del producto y devuelve
   * el detalle de lo que cambiaria. Lanza si alguna regla no se cumple.
   */
  evaluate(product: MachineProduct, requests: readonly PriceChangeRequest[]): PriceChange[] {
    if (requests.length === 0) {
      throw new ValidationError('No se ha indicado ningun precio a cambiar');
    }

    const seen = new Set<PriceKind>();
    const changes: PriceChange[] = [];

    for (const request of requests) {
      if (seen.has(request.kind)) {
        throw new ValidationError(`Precio "${request.kind}" indicado mas de una vez`);
      }
      seen.add(request.kind);

      const previous = product.pricing.get(request.kind) ?? null;
      const variation = previous ? request.newPrice.variationFrom(previous) : null;

      if (
        variation !== null &&
        variation > this.options.maxVariation &&
        !this.options.confirmedLargeChange
      ) {
        throw new PriceChangeTooLargeError(
          previous!.toDecimal(),
          request.newPrice.toDecimal(),
          variation,
          this.options.maxVariation,
        );
      }

      changes.push({
        kind: request.kind,
        previous,
        next: request.newPrice,
        variation,
      });
    }

    return changes;
  }

  /** Cambios que no alteran nada: util para no llamar a Nayax en balde. */
  static isNoop(changes: readonly PriceChange[]): boolean {
    return changes.every((change) => change.previous !== null && change.previous.equals(change.next));
  }
}
