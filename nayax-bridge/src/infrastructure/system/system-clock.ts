import type { ClockPort } from '../../application/ports/support.ports.js';

export class SystemClock implements ClockPort {
  now(): Date {
    return new Date();
  }

  today(): string {
    return this.now().toISOString().slice(0, 10);
  }
}

/** Reloj fijo para tests: hace deterministas los casos de uso con fechas. */
export class FixedClock implements ClockPort {
  constructor(private readonly fixed: Date) {}

  now(): Date {
    return new Date(this.fixed);
  }

  today(): string {
    return this.fixed.toISOString().slice(0, 10);
  }
}
