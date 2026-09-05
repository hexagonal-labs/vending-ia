import { Money } from '../shared/money.js';
import type { MachineId } from '../shared/ids.js';

export type PaymentMethod = 'card' | 'cash' | 'prepaid' | 'other';

/** Ventas agregadas de un dia. */
export interface DailySales {
  readonly date: string;
  readonly revenue: Money;
  readonly transactionCount: number;
  readonly byPaymentMethod: Partial<Record<PaymentMethod, Money>>;
}

/** Ventas agregadas de una maquina en un periodo. */
export interface MachineSales {
  readonly machineId: MachineId;
  readonly machineName: string;
  readonly revenue: Money;
  readonly transactionCount: number;
}

export interface SalesSummary {
  readonly from: string;
  readonly to: string;
  readonly totalRevenue: Money;
  readonly totalTransactions: number;
  readonly days: readonly DailySales[];
}

/** Suma los dias de un resumen. Funcion pura, facil de testear. */
export function summarize(from: string, to: string, days: readonly DailySales[]): SalesSummary {
  const totalRevenue = days.reduce((acc, day) => acc.add(day.revenue), Money.zero());
  const totalTransactions = days.reduce((acc, day) => acc + day.transactionCount, 0);
  return { from, to, totalRevenue, totalTransactions, days };
}
