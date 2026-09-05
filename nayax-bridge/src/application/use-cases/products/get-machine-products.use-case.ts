import type { UseCase } from '../use-case.js';
import type { MachineProductsPort } from '../../ports/nayax.ports.js';
import type { CachePort } from '../../ports/support.ports.js';
import { machineId as toMachineId } from '../../../domain/shared/ids.js';
import type { MachineProduct } from '../../../domain/product/machine-product.js';
import { needsRestock } from '../../../domain/product/machine-product.js';

export interface GetMachineProductsInput {
  readonly machineId: number;
  /** Si es true, devuelve solo los que necesitan reposicion. */
  readonly onlyNeedingRestock?: boolean;
}

export interface GetMachineProductsOutput {
  readonly products: MachineProduct[];
}

export const machineProductsCacheKey = (machineId: number): string =>
  `machine:${machineId}:products`;

/**
 * Devuelve el mapa de productos de una maquina con sus precios y stock.
 * Es el paso previo obligatorio para cambiar un precio: de aqui salen los
 * machineProductId que necesita la escritura.
 */
export class GetMachineProducts
  implements UseCase<GetMachineProductsInput, GetMachineProductsOutput>
{
  constructor(
    private readonly products: MachineProductsPort,
    private readonly cache: CachePort,
  ) {}

  async execute(input: GetMachineProductsInput): Promise<GetMachineProductsOutput> {
    const id = toMachineId(input.machineId);
    const key = machineProductsCacheKey(id);

    let products = await this.cache.get<MachineProduct[]>(key);
    if (!products) {
      products = await this.products.listByMachine(id);
      await this.cache.set(key, products);
    }

    return {
      products: input.onlyNeedingRestock ? products.filter(needsRestock) : products,
    };
  }
}
