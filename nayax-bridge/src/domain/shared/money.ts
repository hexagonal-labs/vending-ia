import { ValidationError } from './errors.js';

const DEFAULT_CURRENCY = 'EUR';

/**
 * Value object de dinero.
 *
 * Se guarda en centimos (entero) para evitar los errores clasicos de coma
 * flotante: 0.1 + 0.2 !== 0.3. Nayax nos manda y espera decimales, asi que la
 * conversion se hace solo en los bordes (fromDecimal / toDecimal).
 */
export class Money {
  private constructor(
    readonly cents: number,
    readonly currency: string,
  ) {}

  static fromDecimal(value: number, currency: string = DEFAULT_CURRENCY): Money {
    if (!Number.isFinite(value)) {
      throw new ValidationError(`Importe no valido: ${value}`);
    }
    if (value < 0) {
      throw new ValidationError(`Un importe no puede ser negativo: ${value}`);
    }
    return new Money(Math.round(value * 100), currency);
  }

  static fromCents(cents: number, currency: string = DEFAULT_CURRENCY): Money {
    if (!Number.isInteger(cents)) {
      throw new ValidationError(`Los centimos deben ser un entero: ${cents}`);
    }
    if (cents < 0) {
      throw new ValidationError(`Un importe no puede ser negativo: ${cents}`);
    }
    return new Money(cents, currency);
  }

  static zero(currency: string = DEFAULT_CURRENCY): Money {
    return new Money(0, currency);
  }

  toDecimal(): number {
    return this.cents / 100;
  }

  isZero(): boolean {
    return this.cents === 0;
  }

  equals(other: Money): boolean {
    return this.cents === other.cents && this.currency === other.currency;
  }

  add(other: Money): Money {
    this.assertSameCurrency(other);
    return new Money(this.cents + other.cents, this.currency);
  }

  /**
   * Variacion relativa respecto a `base`, en valor absoluto.
   * De 1,00 a 1,30 devuelve 0.30. Si la base es 0 no existe variacion
   * porcentual: devuelve Infinity salvo que el nuevo valor tambien sea 0.
   */
  variationFrom(base: Money): number {
    this.assertSameCurrency(base);
    if (base.cents === 0) {
      return this.cents === 0 ? 0 : Number.POSITIVE_INFINITY;
    }
    return Math.abs(this.cents - base.cents) / base.cents;
  }

  toString(): string {
    return `${this.toDecimal().toFixed(2)} ${this.currency}`;
  }

  private assertSameCurrency(other: Money): void {
    if (this.currency !== other.currency) {
      throw new ValidationError(
        `No se pueden mezclar divisas: ${this.currency} y ${other.currency}`,
      );
    }
  }
}
