import type { SalesPort } from '../../application/ports/nayax.ports.js';
import type { MachineId } from '../../domain/shared/ids.js';
import type { DateRange } from '../../domain/shared/date-range.js';
import type { DailySales, MachineSales, PaymentMethod } from '../../domain/sales/sales.js';
import { Money } from '../../domain/shared/money.js';
import { machineId as toMachineIdVo } from '../../domain/shared/ids.js';
import type { NayaxHttpClient } from './nayax-http-client.js';

/**
 * Adaptador de ventas sobre los widgets de Lynx.
 *
 * Lynx no expone un "dame las ventas" limpio: se piden los datos crudos de los
 * mismos widgets del dashboard, via POST a /dashboard/get-widget-data con un
 * screenTypeId y widgetTypeId. Los ids concretos dependen de tu cuenta.
 *
 * PENDIENTE DE VERIFICAR: confirma widgetTypeId y la forma exacta de la
 * respuesta con el conector MCP de Nayax y con una llamada real contra QA.
 * El parseo esta aislado en los metodos privados justo por eso.
 */

const WIDGET_SALES_BY_PERIOD = 193;
const WIDGET_SALES_BY_MACHINE = 194;
const SCREEN_OPERATOR = 1;

interface WidgetRow {
  [key: string]: unknown;
}

export interface NayaxSalesAdapterOptions {
  readonly operatorId: number;
}

export class NayaxSalesAdapter implements SalesPort {
  constructor(
    private readonly http: NayaxHttpClient,
    private readonly options: NayaxSalesAdapterOptions,
  ) {}

  async getDailySales(range: DateRange, machineId?: MachineId): Promise<DailySales[]> {
    const rows = await this.fetchWidget(WIDGET_SALES_BY_PERIOD, range, [
      { name: 'groupBy', value: 'day', type: 'string' },
      ...(machineId ? [{ name: 'machineId', value: String(machineId), type: 'string' }] : []),
    ]);

    return rows.map((row) => this.toDailySales(row));
  }

  async getSalesByMachine(range: DateRange): Promise<MachineSales[]> {
    const rows = await this.fetchWidget(WIDGET_SALES_BY_MACHINE, range, []);
    return rows.map((row) => this.toMachineSales(row));
  }

  private async fetchWidget(
    widgetTypeId: number,
    range: DateRange,
    extraFilters: Array<{ name: string; value: string; type: string }>,
  ): Promise<WidgetRow[]> {
    const response = await this.http.request<unknown>({
      method: 'POST',
      path: '/dashboard/get-widget-data',
      body: {
        screenTypeId: SCREEN_OPERATOR,
        widgetTypeId,
        entityId: this.options.operatorId,
        filters: [
          { name: 'startDate', value: range.from, type: 'Date' },
          { name: 'endDate', value: range.to, type: 'Date' },
          ...extraFilters,
        ],
      },
    });

    return extractRows(response);
  }

  private toDailySales(row: WidgetRow): DailySales {
    const revenue = Money.fromDecimal(readNumber(row, ['Sales', 'Revenue', 'Total', 'Amount']));
    const byPaymentMethod: Partial<Record<PaymentMethod, Money>> = {};

    const card = readOptionalNumber(row, ['CreditCard', 'Card', 'CreditCardSales']);
    const cash = readOptionalNumber(row, ['Cash', 'CashSales']);
    if (card !== null) byPaymentMethod.card = Money.fromDecimal(card);
    if (cash !== null) byPaymentMethod.cash = Money.fromDecimal(cash);

    return {
      date: readString(row, ['Date', 'Day', 'Period', 'TimePeriod']),
      revenue,
      transactionCount: readNumber(row, ['Transactions', 'Vends', 'TransactionCount']),
      byPaymentMethod,
    };
  }

  private toMachineSales(row: WidgetRow): MachineSales {
    const rawId = readNumber(row, ['MachineID', 'MachineId', 'Id']);
    return {
      machineId: toMachineIdVo(rawId > 0 ? rawId : 1),
      machineName: readString(row, ['MachineName', 'Machine', 'Name']),
      revenue: Money.fromDecimal(readNumber(row, ['Sales', 'Revenue', 'Total'])),
      transactionCount: readNumber(row, ['Transactions', 'Vends']),
    };
  }
}

/**
 * Lynx envuelve los datos de forma distinta segun el widget. Normalizamos aqui
 * en vez de esparcir comprobaciones por todo el adaptador.
 */
function extractRows(response: unknown): WidgetRow[] {
  if (Array.isArray(response)) return response as WidgetRow[];
  if (response && typeof response === 'object') {
    const obj = response as Record<string, unknown>;
    for (const key of ['Data', 'data', 'Rows', 'rows', 'Result', 'result']) {
      const value = obj[key];
      if (Array.isArray(value)) return value as WidgetRow[];
    }
  }
  return [];
}

function readNumber(row: WidgetRow, keys: string[]): number {
  return readOptionalNumber(row, keys) ?? 0;
}

function readOptionalNumber(row: WidgetRow, keys: string[]): number | null {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string') {
      const parsed = Number(value.replace(',', '.'));
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  return null;
}

function readString(row: WidgetRow, keys: string[]): string {
  for (const key of keys) {
    const value = row[key];
    if (typeof value === 'string' && value.trim()) return value.trim();
    if (typeof value === 'number') return String(value);
  }
  return '';
}
