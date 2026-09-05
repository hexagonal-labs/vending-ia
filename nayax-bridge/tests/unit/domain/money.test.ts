import { describe, expect, it } from 'vitest';
import { Money } from '../../../src/domain/shared/money.js';
import { ValidationError } from '../../../src/domain/shared/errors.js';

describe('Money', () => {
  it('evita los errores de coma flotante guardando centimos', () => {
    const total = Money.fromDecimal(0.1).add(Money.fromDecimal(0.2));
    expect(total.toDecimal()).toBe(0.3);
  });

  it('rechaza importes negativos', () => {
    expect(() => Money.fromDecimal(-1)).toThrow(ValidationError);
  });

  it('calcula la variacion relativa', () => {
    const previous = Money.fromDecimal(1.0);
    const next = Money.fromDecimal(1.3);
    expect(next.variationFrom(previous)).toBeCloseTo(0.3, 5);
  });

  it('trata la variacion sobre cero como infinita', () => {
    expect(Money.fromDecimal(1).variationFrom(Money.zero())).toBe(Number.POSITIVE_INFINITY);
    expect(Money.zero().variationFrom(Money.zero())).toBe(0);
  });

  it('no mezcla divisas', () => {
    expect(() => Money.fromDecimal(1, 'EUR').add(Money.fromDecimal(1, 'USD'))).toThrow(ValidationError);
  });
});
