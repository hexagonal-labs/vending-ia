import type { FastifyInstance } from 'fastify';
import type { Container } from '../../../container.js';
import { presentMachine } from '../../../shared/presenters.js';
import { presentMachineProductsResponse } from '../../../shared/mcp-contracts.js';
import {
  machineProductsParamsSchema,
  machineProductsQuerySchema,
} from '../../../shared/schemas.js';

/**
 * Rutas de maquinas y su mapa de productos.
 *
 * Los controladores son finos a proposito: validan, llaman al caso de uso y
 * presentan. Ni una regla de negocio aqui.
 */
export async function registerMachineRoutes(app: FastifyInstance, container: Container): Promise<void> {
  app.get('/machines', async () => {
    const { machines } = await container.useCases.listMachines.execute();
    return { machines: machines.map(presentMachine) };
  });

  app.get('/machines/:machineId/products', async (request) => {
    const params = machineProductsParamsSchema.parse(request.params);
    const query = machineProductsQuerySchema.parse(request.query);

    const { products } = await container.useCases.getMachineProducts.execute({
      machineId: params.machineId,
      onlyNeedingRestock: query.onlyNeedingRestock,
    });

    return presentMachineProductsResponse(params.machineId, products);
  });
}
