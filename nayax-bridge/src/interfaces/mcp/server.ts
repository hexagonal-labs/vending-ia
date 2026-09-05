import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { Container } from '../../container.js';
import { registerReadTools } from './tools/read.tools.js';
import { registerWriteTools } from './tools/write.tools.js';

/**
 * Puerta de entrada MCP: la consumen los agentes de IA.
 *
 * Fijate en que este fichero no tiene ni una regla de negocio. Igual que el
 * servidor HTTP, solo traduce: herramienta MCP -> caso de uso -> respuesta.
 * Es literalmente el mismo cerebro con otra boca.
 */
export function buildMcpServer(container: Container): McpServer {
  const server = new McpServer(
    {
      name: 'nayax-bridge',
      version: '0.1.0',
    },
    {
      instructions:
        'Herramientas para operar maquinas de vending con TPV Nayax: consultar ventas, revisar el mapa ' +
        'de productos y cambiar precios. Flujo recomendado para cualquier cambio de precio: ' +
        '1) list_machines para localizar la maquina, 2) list_machine_products para obtener el ' +
        'machineProductId y ver los precios actuales, 3) update_product_price en modo simulacion, ' +
        '4) mostrar el resultado al usuario y esperar su confirmacion explicita, 5) repetir con ' +
        'dryRun=false. Nunca invente ids ni aplique cambios sin confirmacion del usuario.',
    },
  );

  registerReadTools(server, container);

  if (container.config.WRITES_ENABLED || container.config.MCP_WRITES_REQUIRE_DRY_RUN) {
    registerWriteTools(server, container);
  }

  return server;
}
