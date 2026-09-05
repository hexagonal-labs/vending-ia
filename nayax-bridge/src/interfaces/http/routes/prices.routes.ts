import type { FastifyInstance } from 'fastify';
import type { Container } from '../../../container.js';
import { ForbiddenError } from '../../../domain/shared/errors.js';
import { bulkUpdateBodySchema, updatePriceBodySchema, updatePriceParamsSchema } from '../../../shared/schemas.js';

/**
 * Rutas de escritura de precios.
 *
 * Nota de diseno: dryRun por defecto es TRUE en el esquema. Para aplicar un
 * cambio de verdad hay que pedirlo explicitamente. Es una friccion buscada:
 * estas tocando maquinas que cobran dinero real.
 */
export async function registerPriceRoutes(app: FastifyInstance, container: Container): Promise<void> {
  app.put('/machines/:machineId/products/:machineProductId/prices', async (request) => {
    const params = updatePriceParamsSchema.parse(request.params);
    const body = updatePriceBodySchema.parse(request.body);
    const actor = requireActor(request.actor);

    return container.useCases.updateProductPrice.execute({
      machineId: params.machineId,
      machineProductId: params.machineProductId,
      prices: body.prices,
      dryRun: body.dryRun,
      confirmLargeChange: body.confirmLargeChange,
      actor,
    });
  });

  app.post('/prices/bulk', async (request) => {
    const body = bulkUpdateBodySchema.parse(request.body);
    const actor = requireActor(request.actor);

    return container.useCases.bulkUpdatePrices.execute({
      items: body.items,
      dryRun: body.dryRun,
      confirmLargeChange: body.confirmLargeChange,
      actor,
    });
  });

  app.get('/audit', async (request) => {
    const actor = requireActor(request.actor);
    if (actor.role === 'viewer') {
      throw new ForbiddenError('El rol "viewer" no puede consultar la auditoria.');
    }
    const entries = await container.audit.list(100);
    return { count: entries.length, entries };
  });
}

function requireActor(actor: import('../../../application/ports/support.ports.js').Actor | undefined) {
  if (!actor) {
    throw new ForbiddenError('Peticion sin identificar');
  }
  return actor;
}
