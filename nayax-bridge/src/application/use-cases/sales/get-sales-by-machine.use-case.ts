import type { UseCase } from '../use-case.js';
import type { SalesPort } from '../../ports/nayax.ports.js';
import type { ClockPort } from '../../ports/support.ports.js';
import { DateRange } from '../../../domain/shared/date-range.js';
import type { MachineSales } from '../../../domain/sales/sales.js';

export interface GetSalesByMachineInput {
  readonly from?: string;
  readonly to?: string;
}

export interface GetSalesByMachineOutput {
  readonly from: string;
  readonly to: string;
  readonly machines: readonly MachineSales[];
}

/** Ranking de maquinas por facturacion en un periodo. */
export class GetSalesByMachine
  implements UseCase<GetSalesByMachineInput, GetSalesByMachineOutput>
{
  constructor(
    private readonly sales: SalesPort,
    private readonly clock: ClockPort,
  ) {}

  async execute(input: GetSalesByMachineInput): Promise<GetSalesByMachineOutput> {
    const today = this.clock.today();
    const range = DateRange.create(input.from ?? today, input.to ?? input.from ?? today);
    const machines = await this.sales.getSalesByMachine(range);

    return {
      from: range.from,
      to: range.to,
      machines: [...machines].sort((a, b) => b.revenue.cents - a.revenue.cents),
    };
  }
}
