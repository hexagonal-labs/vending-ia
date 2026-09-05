import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { Container } from '../../../container.js';
import { presentMachine, presentMachineSales, presentSalesSummary } from '../../../shared/presenters.js';
import { presentMachineProductsResponse } from '../../../shared/mcp-contracts.js';
import { asJson, withErrorHandling } from './tool-helpers.js';

/**
 * Herramientas de LECTURA para agentes de IA.
 *
 * Las descripciones son largas a proposito: el agente decide que llamar
 * leyendolas. Una descripcion vaga ("consulta productos") provoca llamadas
 * equivocadas; una que explica que devuelve, que necesita y con que otra
 * herramienta se encadena, no.
 */
export function registerReadTools(server: McpServer, container: Container): void {
  server.registerTool(
    'list_machines',
    {
      title: 'Listar maquinas',
      description:
        'Devuelve todas las maquinas de vending del operador con su id, nombre, ubicacion y estado. ' +
        'Uselo como primer paso cuando el usuario mencione una maquina por su nombre y necesite el machineId ' +
        'para otras herramientas. Los resultados se cachean unos segundos.',
      inputSchema: {},
      annotations: { readOnlyHint: true },
    },
    withErrorHandling(async () => {
      const { machines } = await container.useCases.listMachines.execute();
      return asJson({ count: machines.length, machines: machines.map(presentMachine) });
    }),
  );

  server.registerTool(
    'list_machine_products',
    {
      title: 'Listar productos de una maquina',
      description:
        'Devuelve el mapa de productos de una maquina: el nombre real ProductName de catalogo, codigo de ' +
        'seleccion, todos los precios (cash, card, prepaid, machine, retail), estado de stock, baja rotacion ' +
        'y la ficha completa de catalogo en catalogProduct. ' +
        'La respuesta sigue el contrato nayax-machine-products/v1; para margenes use exclusivamente prices.machine ' +
        '(MachinePrice), que es el PVP configurado en la maquina. ' +
        'ES EL PASO OBLIGATORIO ANTES DE CAMBIAR UN PRECIO, porque de aqui sale el machineProductId que ' +
        'necesita update_product_price. Si necesita el machineId, obtengalo antes con list_machines.',
      inputSchema: {
        machineId: z.number().int().positive().describe('Id de la maquina, obtenido con list_machines'),
        onlyNeedingRestock: z
          .boolean()
          .optional()
          .describe('Si es true, devuelve solo los productos que necesitan reposicion'),
      },
      annotations: { readOnlyHint: true },
    },
    withErrorHandling(async ({ machineId, onlyNeedingRestock }) => {
      const { products } = await container.useCases.getMachineProducts.execute({
        machineId,
        onlyNeedingRestock,
      });
      return asJson(presentMachineProductsResponse(machineId, products));
    }),
  );

  server.registerTool(
    'get_sales_summary',
    {
      title: 'Resumen de ventas por dia',
      description:
        'Devuelve la facturacion y el numero de transacciones por dia en un rango de fechas, con el total ' +
        'del periodo y el desglose por medio de pago. Si no se indican fechas usa el dia de hoy. ' +
        'Opcionalmente se puede filtrar por una maquina concreta. Use esta herramienta para preguntas del ' +
        'tipo "cuanto vendi ayer" o "como fue la ultima semana".',
      inputSchema: {
        from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe('Fecha inicial YYYY-MM-DD'),
        to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe('Fecha final YYYY-MM-DD'),
        machineId: z.number().int().positive().optional().describe('Filtrar por una maquina concreta'),
      },
      annotations: { readOnlyHint: true },
    },
    withErrorHandling(async (input) => {
      const summary = await container.useCases.getSalesSummary.execute(input);
      return asJson(presentSalesSummary(summary));
    }),
  );

  server.registerTool(
    'get_sales_by_machine',
    {
      title: 'Ranking de ventas por maquina',
      description:
        'Devuelve la facturacion de cada maquina en un periodo, ordenada de mayor a menor. Util para ' +
        'identificar que maquinas rinden mejor o peor. Si no se indican fechas usa el dia de hoy.',
      inputSchema: {
        from: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe('Fecha inicial YYYY-MM-DD'),
        to: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional().describe('Fecha final YYYY-MM-DD'),
      },
      annotations: { readOnlyHint: true },
    },
    withErrorHandling(async (input) => {
      const result = await container.useCases.getSalesByMachine.execute(input);
      return asJson({
        from: result.from,
        to: result.to,
        machines: result.machines.map(presentMachineSales),
      });
    }),
  );

  server.registerTool(
    'get_price_change_history',
    {
      title: 'Historial de cambios de precio',
      description:
        'Devuelve el registro de auditoria de los ultimos cambios de precio: quien los hizo, cuando, ' +
        'sobre que producto y con que valores antes y despues. Incluye tambien las simulaciones (dryRun). ' +
        'Use esta herramienta antes de proponer un cambio, para no repetir uno reciente.',
      inputSchema: {
        limit: z.number().int().positive().max(200).optional().describe('Numero de entradas (por defecto 20)'),
      },
      annotations: { readOnlyHint: true },
    },
    withErrorHandling(async ({ limit }) => {
      const entries = await container.audit.list(limit ?? 20);
      return asJson({ count: entries.length, entries });
    }),
  );
}
