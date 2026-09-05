import { ValidationError } from './errors.js';

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** Rango de fechas cerrado (ambos extremos incluidos), en formato YYYY-MM-DD. */
export class DateRange {
  private constructor(
    readonly from: string,
    readonly to: string,
  ) {}

  static create(from: string, to: string): DateRange {
    if (!ISO_DATE.test(from) || !ISO_DATE.test(to)) {
      throw new ValidationError(`Las fechas deben tener formato YYYY-MM-DD: ${from} / ${to}`);
    }
    if (from > to) {
      throw new ValidationError(`La fecha inicial ${from} es posterior a la final ${to}`);
    }
    return new DateRange(from, to);
  }

  static singleDay(day: string): DateRange {
    return DateRange.create(day, day);
  }

  get days(): number {
    const ms = Date.parse(`${this.to}T00:00:00Z`) - Date.parse(`${this.from}T00:00:00Z`);
    return Math.round(ms / 86_400_000) + 1;
  }

  toString(): string {
    return `${this.from}..${this.to}`;
  }
}
