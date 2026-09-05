import type { UseCase } from '../use-case.js';
import type { MachinesPort } from '../../ports/nayax.ports.js';
import type { CachePort } from '../../ports/support.ports.js';
import type { Machine } from '../../../domain/machine/machine.js';

export interface ListMachinesOutput {
  readonly machines: Machine[];
}

const CACHE_KEY = 'machines:list';

/**
 * Lista las maquinas del operador.
 * Cachea porque el parque de maquinas cambia poquisimo y no tiene sentido
 * castigar la API de Nayax en cada carga de pantalla.
 */
export class ListMachines implements UseCase<void, ListMachinesOutput> {
  constructor(
    private readonly machines: MachinesPort,
    private readonly cache: CachePort,
  ) {}

  async execute(): Promise<ListMachinesOutput> {
    const cached = await this.cache.get<Machine[]>(CACHE_KEY);
    if (cached) {
      return { machines: cached };
    }

    const machines = await this.machines.listMachines();
    await this.cache.set(CACHE_KEY, machines);
    return { machines };
  }
}
