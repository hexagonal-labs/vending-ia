import type { MachineId, MachineProductId } from '../../domain/shared/ids.js';
import type { Machine } from '../../domain/machine/machine.js';
import type { MachineProduct } from '../../domain/product/machine-product.js';
import type { PriceKind } from '../../domain/product/pricing.js';
import type { DailySales, MachineSales } from '../../domain/sales/sales.js';
import type { DateRange } from '../../domain/shared/date-range.js';

/**
 * Puertos hacia Nayax.
 *
 * Estan separados a proposito (ISP): un caso de uso de ventas no deberia
 * depender de un contrato que ademas sabe escribir precios.
 */

export interface MachinesPort {
  listMachines(): Promise<Machine[]>;
  getMachine(id: MachineId): Promise<Machine | null>;
}

export interface MachineProductsPort {
  listByMachine(machineId: MachineId): Promise<MachineProduct[]>;
  getById(machineId: MachineId, productId: MachineProductId): Promise<MachineProduct | null>;
}

export interface PriceWriterPort {
  updatePrices(
    machineId: MachineId,
    productId: MachineProductId,
    prices: Partial<Record<PriceKind, number>>,
  ): Promise<MachineProduct>;
}

export interface SalesPort {
  getDailySales(range: DateRange, machineId?: MachineId): Promise<DailySales[]>;
  getSalesByMachine(range: DateRange): Promise<MachineSales[]>;
}
