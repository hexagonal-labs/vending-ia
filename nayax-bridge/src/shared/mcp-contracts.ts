import type { MachineProduct } from '../domain/product/machine-product.js';
import { presentMachineProduct, type MachineProductView } from './presenters.js';

/**
 * Contrato consumido por workflows externos para consultar productos Nayax.
 * Se versiona de forma explícita para que un cambio incompatible no silencie
 * errores de cálculo en el agente de pricing.
 */
export const NAYAX_MACHINE_PRODUCTS_CONTRACT_VERSION = 'nayax-machine-products/v1' as const;

export interface MachineProductsResponseV1 {
  contractVersion: typeof NAYAX_MACHINE_PRODUCTS_CONTRACT_VERSION;
  machineId: number;
  count: number;
  products: MachineProductView[];
}

export function presentMachineProductsResponse(
  machineId: number,
  products: readonly MachineProduct[],
): MachineProductsResponseV1 {
  return {
    contractVersion: NAYAX_MACHINE_PRODUCTS_CONTRACT_VERSION,
    machineId,
    count: products.length,
    products: products.map(presentMachineProduct),
  };
}
