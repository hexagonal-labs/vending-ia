import type { CatalogProduct, MachineProduct } from '../domain/product/machine-product.js';
import { needsRestock } from '../domain/product/machine-product.js';
import type { Machine } from '../domain/machine/machine.js';
import type { MachineSales, SalesSummary } from '../domain/sales/sales.js';

/**
 * Presentadores: entidad de dominio -> JSON plano de respuesta.
 *
 * Sirven a las dos puertas de entrada. Importante para MCP: devolvemos objetos
 * compactos, no los 30 campos de Lynx. Cada campo de mas es contexto que le
 * quitamos al agente.
 */

export interface MachineProductView {
  machineProductId: string;
  machineId: number;
  nayaxProductId: number | null;
  name: string;
  catalogProduct: CatalogProduct | null;
  selectionCode: string | null;
  prices: Record<string, number>;
  stock: { par: number | null; missing: number | null; alertThreshold: number | null };
  needsRestock: boolean;
  slowMover: boolean;
  lastSaleAt: string | null;
}

export function presentMachineProduct(product: MachineProduct): MachineProductView {
  return {
    machineProductId: product.machineProductId,
    machineId: product.machineId,
    nayaxProductId: product.nayaxProductId,
    name: product.name,
    catalogProduct: product.catalogProduct,
    selectionCode: product.selectionCode,
    prices: product.pricing.toDecimals() as Record<string, number>,
    stock: {
      par: product.stock.par,
      missing: product.stock.missing,
      alertThreshold: product.stock.alertThreshold,
    },
    needsRestock: needsRestock(product),
    slowMover: product.slowMover,
    lastSaleAt: product.lastSaleAt,
  };
}

export function presentMachine(machine: Machine): Record<string, unknown> {
  return {
    machineId: machine.machineId,
    name: machine.name,
    siteName: machine.siteName,
    status: machine.status,
    lastSeenAt: machine.lastSeenAt,
  };
}

export function presentSalesSummary(summary: SalesSummary): Record<string, unknown> {
  return {
    from: summary.from,
    to: summary.to,
    totalRevenue: summary.totalRevenue.toDecimal(),
    currency: summary.totalRevenue.currency,
    totalTransactions: summary.totalTransactions,
    days: summary.days.map((day) => ({
      date: day.date,
      revenue: day.revenue.toDecimal(),
      transactions: day.transactionCount,
      byPaymentMethod: Object.fromEntries(
        Object.entries(day.byPaymentMethod).map(([method, money]) => [method, money.toDecimal()]),
      ),
    })),
  };
}

export function presentMachineSales(sales: MachineSales): Record<string, unknown> {
  return {
    machineId: sales.machineId,
    machineName: sales.machineName,
    revenue: sales.revenue.toDecimal(),
    transactions: sales.transactionCount,
  };
}
