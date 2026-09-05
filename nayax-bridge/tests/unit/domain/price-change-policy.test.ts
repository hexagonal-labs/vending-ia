import { describe, expect, it } from 'vitest';
import { PriceChangePolicy } from '../../../src/domain/product/price-change-policy.js';
import { Pricing } from '../../../src/domain/product/pricing.js';
import { Money } from '../../../src/domain/shared/money.js';
import { PriceChangeTooLargeError, ValidationError } from '../../../src/domain/shared/errors.js';
import { machineId, machineProductId } from '../../../src/domain/shared/ids.js';
import type { MachineProduct } from '../../../src/domain/product/machine-product.js';

const product: MachineProduct = {
  machineProductId: machineProductId('101'),
  machineId: machineId(5001),
  nayaxProductId: null,
  catalogProduct: null,
  name: 'Coca-Cola Zero',
  selectionCode: 'A1',
  pricing: Pricing.fromDecimals({ cash: 1.5, card: 1.6 }),
  stock: { par: 10, missing: 2, alertThreshold: 3 },
  lastSaleAt: null,
  slowMover: false,
};

describe('PriceChangePolicy', () => {
  const policy = (confirmed = false) =>
    new PriceChangePolicy({ maxVariation: 0.3, confirmedLargeChange: confirmed });

  it('acepta un cambio dentro del limite', () => {
    const changes = policy().evaluate(product, [
      { kind: 'card', newPrice: Money.fromDecimal(1.8) },
    ]);

    expect(changes).toHaveLength(1);
    expect(changes[0]!.previous?.toDecimal()).toBe(1.6);
    expect(changes[0]!.next.toDecimal()).toBe(1.8);
  });

  it('bloquea un cambio que supera el limite', () => {
    expect(() =>
      policy().evaluate(product, [{ kind: 'card', newPrice: Money.fromDecimal(3.0) }]),
    ).toThrow(PriceChangeTooLargeError);
  });

  it('permite el cambio grande si se confirma explicitamente', () => {
    const changes = policy(true).evaluate(product, [
      { kind: 'card', newPrice: Money.fromDecimal(3.0) },
    ]);
    expect(changes[0]!.next.toDecimal()).toBe(3.0);
  });

  it('permite fijar un precio que antes no existia', () => {
    const changes = policy().evaluate(product, [
      { kind: 'prepaid', newPrice: Money.fromDecimal(1.4) },
    ]);
    expect(changes[0]!.previous).toBeNull();
    expect(changes[0]!.variation).toBeNull();
  });

  it('rechaza el mismo tipo de precio dos veces', () => {
    expect(() =>
      policy().evaluate(product, [
        { kind: 'card', newPrice: Money.fromDecimal(1.7) },
        { kind: 'card', newPrice: Money.fromDecimal(1.8) },
      ]),
    ).toThrow(ValidationError);
  });

  it('detecta cambios que no cambian nada', () => {
    const changes = policy().evaluate(product, [
      { kind: 'card', newPrice: Money.fromDecimal(1.6) },
    ]);
    expect(PriceChangePolicy.isNoop(changes)).toBe(true);
  });
});
