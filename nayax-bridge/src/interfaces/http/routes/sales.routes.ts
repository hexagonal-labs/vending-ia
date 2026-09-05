import type { FastifyInstance } from 'fastify';
import type { Container } from '../../../container.js';
import { presentMachineSales, presentSalesSummary } from '../../../shared/presenters.js';
import { salesQuerySchema } from '../../../shared/schemas.js';

export async function registerSalesRoutes(app: FastifyInstance, container: Container): Promise<void> {
  app.get('/sales/summary', async (request) => {
    const query = salesQuerySchema.parse(request.query);
    const summary = await container.useCases.getSalesSummary.execute(query);
    return presentSalesSummary(summary);
  });

  app.get('/sales/by-machine', async (request) => {
    const query = salesQuerySchema.parse(request.query);
    const result = await container.useCases.getSalesByMachine.execute({
      from: query.from,
      to: query.to,
    });

    return {
      from: result.from,
      to: result.to,
      machines: result.machines.map(presentMachineSales),
    };
  });
}
