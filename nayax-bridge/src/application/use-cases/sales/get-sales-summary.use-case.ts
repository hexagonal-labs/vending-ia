import type { UseCase } from '../use-case.js';
import type { SalesPort } from '../../ports/nayax.ports.js';
import type { ClockPort } from '../../ports/support.ports.js';
import { DateRange } from '../../../domain/shared/date-range.js';
import { machineId as toMachineId } from '../../../domain/shared/ids.js';
import { summarize, type SalesSummary } from '../../../domain/sales/sales.js';

export interface GetSalesSummaryInput {
  /** YYYY-MM-DD. Si se omite, se usa hoy. */
  readonly from?: string;
  readonly to?: string;
  readonly machineId?: number;
}

export type GetSalesSummaryOutput = SalesSummary;

/** Resumen de ventas por dia, con totales del periodo. */
export class GetSalesSummary implements UseCase<GetSalesSummaryInput, GetSalesSummaryOutput> {
  constructor(
    private readonly sales: SalesPort,
    private readonly clock: ClockPort,
  ) {}

  async execute(input: GetSalesSummaryInput): Promise<GetSalesSummaryOutput> {
    const today = this.clock.today();
    const range = DateRange.create(input.from ?? today, input.to ?? input.from ?? today);
    const machine = input.machineId === undefined ? undefined : toMachineId(input.machineId);

    const days = await this.sales.getDailySales(range, machine);
    return summarize(range.from, range.to, days);
  }
}
