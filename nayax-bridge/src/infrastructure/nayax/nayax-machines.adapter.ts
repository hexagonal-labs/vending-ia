import type { MachinesPort } from '../../application/ports/nayax.ports.js';
import type { MachineId } from '../../domain/shared/ids.js';
import type { Machine } from '../../domain/machine/machine.js';
import type { NayaxHttpClient } from './nayax-http-client.js';
import type { NayaxMachineDto } from './nayax.dto.js';
import { toMachine } from './nayax.mappers.js';

/**
 * Adaptador de maquinas sobre Lynx.
 *
 * Endpoints usados (verificar contra la doc con el conector MCP de Nayax):
 *   GET /machines
 *   GET /machines/{machineId}
 */
export class NayaxMachinesAdapter implements MachinesPort {
  constructor(private readonly http: NayaxHttpClient) {}

  async listMachines(): Promise<Machine[]> {
    const response = await this.http.request<NayaxMachineDto[]>({
      method: 'GET',
      path: '/machines',
    });

    return (response ?? []).filter((dto) => Boolean(dto.MachineID)).map(toMachine);
  }

  async getMachine(id: MachineId): Promise<Machine | null> {
    const response = await this.http.request<NayaxMachineDto | null>({
      method: 'GET',
      path: `/machines/${id}`,
    });

    if (!response?.MachineID) return null;
    return toMachine(response);
  }
}
