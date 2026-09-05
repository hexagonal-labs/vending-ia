import { ValidationError } from './errors.js';

/**
 * Ids como tipos nominales (branded types). Evita el bug tipico de pasar un
 * machineProductId donde iba un machineId. Los IDs de producto de maquina
 * pueden superar la precision segura de los numeros de JavaScript, por eso se
 * conservan como strings.
 */
export type MachineId = number & { readonly __brand: 'MachineId' };
export type MachineProductId = string & { readonly __brand: 'MachineProductId' };
export type NayaxProductId = number & { readonly __brand: 'NayaxProductId' };

function assertPositiveInt(value: number, name: string): void {
  if (!Number.isInteger(value) || value <= 0) {
    throw new ValidationError(`${name} debe ser un entero positivo, recibido: ${value}`);
  }
}

export function machineId(value: number): MachineId {
  assertPositiveInt(value, 'machineId');
  return value as MachineId;
}

export function machineProductId(value: string | number): MachineProductId {
  const normalized = typeof value === 'number' ? normalizeSafeNumber(value, 'machineProductId') : value.trim();
  if (!/^[1-9]\d*$/.test(normalized)) {
    throw new ValidationError(`machineProductId debe ser un entero positivo, recibido: ${value}`);
  }
  return normalized as MachineProductId;
}

function normalizeSafeNumber(value: number, name: string): string {
  if (!Number.isSafeInteger(value) || value <= 0) {
    throw new ValidationError(
      `${name} debe recibirse como string cuando supera la precision segura de JavaScript, recibido: ${value}`,
    );
  }
  return String(value);
}

export function nayaxProductId(value: number): NayaxProductId {
  assertPositiveInt(value, 'nayaxProductId');
  return value as NayaxProductId;
}
