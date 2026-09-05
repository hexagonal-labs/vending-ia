import { buildContainer } from './container.js';
import { buildHttpServer } from './interfaces/http/server.js';

/** Arranque del servidor HTTP. */
async function main(): Promise<void> {
  const container = buildContainer();
  const app = await buildHttpServer(container);

  const { HTTP_PORT, HTTP_HOST } = container.config;
  await app.listen({ port: HTTP_PORT, host: HTTP_HOST });

  container.logger.info(
    { port: HTTP_PORT, host: HTTP_HOST, nayax: container.config.NAYAX_BASE_URL },
    'API puente Nayax escuchando',
  );

  const shutdown = async (signal: string): Promise<void> => {
    container.logger.info({ signal }, 'Cerrando servidor');
    await app.close();
    process.exit(0);
  };

  process.on('SIGINT', () => void shutdown('SIGINT'));
  process.on('SIGTERM', () => void shutdown('SIGTERM'));
}

main().catch((error) => {
  console.error('Fallo al arrancar:', error instanceof Error ? error.message : error);
  process.exit(1);
});
