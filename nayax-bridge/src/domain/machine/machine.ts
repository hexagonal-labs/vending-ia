import type { MachineId } from '../shared/ids.js';

export type MachineStatus = 'online' | 'offline' | 'unknown';

/** Una maquina de vending con TPV Nayax. */
export interface Machine {
  readonly machineId: MachineId;
  readonly name: string;
  readonly siteName: string | null;
  readonly status: MachineStatus;
  readonly lastSeenAt: string | null;
}
