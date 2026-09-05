import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { buildContainer } from './container.js';
import { buildMcpServer } from './interfaces/mcp/server.js';

/**
 * Arranque del servidor MCP por stdio.
 *
 * Cuidado: en stdio el protocolo viaja por stdout. Cualquier console.log
 * rompe la sesion. Por eso los logs van a stderr (quietLogs) y aqui no se
 * imprime nada a stdout.
 */
async function main(): Promise<void> {
  const container = buildContainer({ quietLogs: true });
  const server = buildMcpServer(container);
  const transport = new StdioServerTransport();

  await server.connect(transport);
  container.logger.info({ nayax: container.config.NAYAX_BASE_URL }, 'Servidor MCP nayax-bridge listo');
}

main().catch((error) => {
  process.stderr.write(`Fallo al arrancar el servidor MCP: ${error instanceof Error ? error.message : String(error)}\n`);
  process.exit(1);
});
