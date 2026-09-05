import { describe, expect, it } from 'vitest';
import { NayaxMachineProductsAdapter } from '../../../src/infrastructure/nayax/nayax-machine-products.adapter.js';
import type { NayaxHttpClient } from '../../../src/infrastructure/nayax/nayax-http-client.js';
import { machineId } from '../../../src/domain/shared/ids.js';

describe('NayaxMachineProductsAdapter', () => {
  it('enriquece productos por ProductRef, deduplica ids y conserva fallos parciales', async () => {
    const requestedPaths: string[] = [];
    const http = {
      request: async <T>(options: { path: string }): Promise<T> => {
        requestedPaths.push(options.path);
        if (options.path === '/machines/5001/machineProducts') {
          return [
            { MachineProductID: '1', MachineID: 5001, ProductRef: 'v1/products/11' },
            { MachineProductID: '2', MachineID: 5001, ProductRef: 'v1/products/11' },
            { MachineProductID: '3', MachineID: 5001, NayaxProductID: 12 },
          ] as T;
        }
        if (options.path === '/products/11') {
          return { NayaxProductID: 11, ProductName: 'Producto maestro' } as T;
        }
        throw new Error('Producto no encontrado');
      },
    } as unknown as NayaxHttpClient;
    const adapter = new NayaxMachineProductsAdapter(http);

    const products = await adapter.listByMachine(machineId(5001));

    expect(requestedPaths).toEqual([
      '/machines/5001/machineProducts',
      '/products/11',
      '/products/12',
    ]);
    expect(products.map((product) => product.name)).toEqual([
      'Producto maestro',
      'Producto maestro',
      'Producto 3',
    ]);
    expect(products[0]?.catalogProduct?.productName).toBe('Producto maestro');
    expect(products[2]?.catalogProduct).toBeNull();
  });
});
