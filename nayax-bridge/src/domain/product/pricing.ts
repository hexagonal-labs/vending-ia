import { Money } from '../shared/money.js';
import { ValidationError } from '../shared/errors.js';

/**
 * Nayax maneja varios precios por producto segun el medio de pago.
 * Este es el vocabulario del dominio; el mapeo a los nombres de Nayax
 * (CashPrice, CreditCardPrice...) vive en el adaptador, no aqui.
 */
export type PriceKind = 'cash' | 'card' | 'prepaid' | 'machine' | 'retail';

export const PRICE_KINDS: readonly PriceKind[] = [
  'cash',
  'card',
  'prepaid',
  'machine',
  'retail',
] as const;

export type PriceMap = Partial<Record<PriceKind, Money>>;

/**
 * Conjunto de precios de un producto. Value object inmutable.
 */
export class Pricing {
  private constructor(private readonly prices: PriceMap) {}

  static from(prices: PriceMap): Pricing {
    return new Pricing({ ...prices });
  }

  static fromDecimals(values: Partial<Record<PriceKind, number | null | undefined>>): Pricing {
    const prices: PriceMap = {};
    for (const kind of PRICE_KINDS) {
      const value = values[kind];
      if (value !== null && value !== undefined) {
        prices[kind] = Money.fromDecimal(value);
      }
    }
    return new Pricing(prices);
  }

  get(kind: PriceKind): Money | undefined {
    return this.prices[kind];
  }

  has(kind: PriceKind): boolean {
    return this.prices[kind] !== undefined;
  }

  /** Devuelve una copia con los precios indicados reemplazados. */
  with(changes: PriceMap): Pricing {
    return new Pricing({ ...this.prices, ...changes });
  }

  /** Los tipos de precio definidos en este conjunto. */
  definedKinds(): PriceKind[] {
    return PRICE_KINDS.filter((kind) => this.prices[kind] !== undefined);
  }

  /**
   * El precio de referencia de cara al cliente es MachinePrice: el PVP que
   * está configurado para esa selección concreta de la máquina.
   */
  reference(): Money {
    const found = this.get('machine') ?? this.get('card') ?? this.get('cash') ?? this.get('retail');
    if (!found) {
      throw new ValidationError('El producto no tiene ningun precio definido');
    }
    return found;
  }

  toDecimals(): Partial<Record<PriceKind, number>> {
    const out: Partial<Record<PriceKind, number>> = {};
    for (const kind of this.definedKinds()) {
      out[kind] = this.prices[kind]!.toDecimal();
    }
    return out;
  }
}
