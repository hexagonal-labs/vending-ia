import Fastify, { type FastifyInstance } from 'fastify';
import type { Container } from '../../container.js';
import { createAuthHook } from './middlewares/auth.js';
import { createErrorHandler } from './middlewares/error-handler.js';
import { registerMachineRoutes } from './routes/machines.routes.js';
import { registerPriceRoutes } from './routes/prices.routes.js';
import { registerSalesRoutes } from './routes/sales.routes.js';

/**
 * Puerta de entrada HTTP: la consume la aplicacion frontal.
 *
 * Es un adaptador, no el cerebro. Toda la logica vive en los casos de uso, que
 * son los mismos que usa el servidor MCP.
 */
export async function buildHttpServer(container: Container): Promise<FastifyInstance> {
  const app = Fastify({ logger: false });

  app.setErrorHandler(createErrorHandler(container.logger));
  app.addHook('onRequest', createAuthHook(container.config));

  app.get('/health', async () => ({
    status: 'ok',
    env: container.config.NODE_ENV,
    writesEnabled: container.config.WRITES_ENABLED,
    nayaxBaseUrl: container.config.NAYAX_BASE_URL,
  }));

  await app.register(
    async (instance) => {
      await registerMachineRoutes(instance, container);
      await registerSalesRoutes(instance, container);
      await registerPriceRoutes(instance, container);
    },
    { prefix: '/api/v1' },
  );

  return app;
}
