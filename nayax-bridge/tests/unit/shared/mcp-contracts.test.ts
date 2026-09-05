import { describe, expect, it } from 'vitest';
import { toMachineProduct } from '../../../src/infrastructure/nayax/nayax.mappers.js';
import { presentMachineProductsResponse } from '../../../src/shared/mcp-contracts.js';

describe('contrato de productos de máquina para MCP', () => {
  it('incluye una versión explícita y MachinePrice', () => {
    const response = presentMachineProductsResponse(5001, [
      toMachineProduct({
        MachineProductID: '3',
        MachineID: 5001,
        NayaxProductID: 1101,
        DEXProductName: 'Agua mineral 50 cl',
        MachinePrice: 1.8,
        CashPrice: 1.7,
      }),
    ]);

    expect(response).toMatchObject({
      contractVersion: 'nayax-machine-products/v1',
      machineId: 5001,
      count: 1,
      products: [{ prices: { machine: 1.8, cash: 1.7 } }],
    });
  });
});
