import { z } from 'zod';
import type { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import type { Container } from '../../../container.js';
import type { Actor } from '../../../application/ports/support.ports.js';
import { asJson, withErrorHandling } from './tool-helpers.js';
import { machineProductIdSchema } from '../../../shared/schemas.js';

/**
 * Herramientas de ESCRITURA para agentes de IA.
 *
 * Aqui es donde un agente puede afectar al mundo real: una maquina pasara a
 * cobrar otra cantidad. Salvaguardas aplicadas:
 *
 *   1. dryRun por defecto TRUE. El agente tiene que pedir explicitamente
 *      aplicar el cambio; simular es gratis y es lo que ocurre si duda.
 *   2. MCP_WRITES_REQUIRE_DRY_RUN=true fuerza que TODO sea simulacion, util
 *      mientras pruebas agentes nuevos.
 *   3. Cambios grandes exigen confirmLargeChange, y la descripcion le dice al
 *      agente que eso lo decide el humano, no el.
 *   4. Todo queda auditado, incluidas las simulaciones.
 */

/** Identidad del agente. Se distingue del canal HTTP para poder auditarlo aparte. */
const MCP_ACTOR: Actor = { id: 'mcp-agent', role: 'agent', channel: 'mcp' };

export function registerWriteTools(server: McpServer, container: Container): void {
  const forceDryRun = container.config.MCP_WRITES_REQUIRE_DRY_RUN;

  const dryRunNote = forceDryRun
    ? ' NOTA: esta instancia esta en modo solo-simulacion, ningun cambio se aplicara realmente.'
    : '';

  server.registerTool(
    'update_product_price',
    {
      title: 'Cambiar el precio de un producto',
      description:
        'Cambia uno o varios precios de un producto en una maquina concreta. Necesita machineId y ' +
        'machineProductId, que se obtienen con list_machine_products (no los invente nunca). ' +
        'Los precios van en euros: por ejemplo 1.80 para 1,80 EUR. ' +
        'Puede indicar cualquier combinacion de: cash (efectivo), card (tarjeta), prepaid (monedero), ' +
        'machine (precio grabado en la maquina) y retail. ' +
        'POR DEFECTO SOLO SIMULA (dryRun=true): devuelve que cambiaria sin tocar nada. ' +
        'Ejecute siempre primero la simulacion, muestre el resultado al usuario y solo pase dryRun=false ' +
        'cuando el usuario lo confirme de forma explicita. ' +
        'Si el cambio supera el limite de variacion configurado, la operacion falla y hay que repetirla ' +
        'con confirmLargeChange=true, decision que debe tomar el usuario, no usted.' +
        dryRunNote,
      inputSchema: {
        machineId: z.number().int().positive().describe('Id de la maquina'),
        machineProductId: machineProductIdSchema.describe(
          'Id del producto en esa maquina, como cadena exacta obtenida con list_machine_products',
        ),
        prices: z
          .object({
            cash: z.number().nonnegative().optional(),
            card: z.number().nonnegative().optional(),
            prepaid: z.number().nonnegative().optional(),
            machine: z.number().nonnegative().optional(),
            retail: z.number().nonnegative().optional(),
          })
          .describe('Precios nuevos en euros. Indique solo los que cambian.'),
        dryRun: z
          .boolean()
          .default(true)
          .describe('true = solo simula (por defecto). false = aplica el cambio de verdad.'),
        confirmLargeChange: z
          .boolean()
          .default(false)
          .describe('Solo si el usuario confirma un cambio que supera el limite de variacion.'),
      },
      annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true },
    },
    withErrorHandling(async (input) => {
      const result = await container.useCases.updateProductPrice.execute({
        machineId: input.machineId,
        machineProductId: input.machineProductId,
        prices: input.prices,
        dryRun: forceDryRun ? true : input.dryRun,
        confirmLargeChange: input.confirmLargeChange,
        actor: MCP_ACTOR,
      });

      return asJson({
        ...result,
        message: result.applied
          ? 'Cambio aplicado en Nayax.'
          : 'Simulacion. No se ha modificado nada. Para aplicarlo, vuelva a llamar con dryRun=false tras confirmarlo con el usuario.',
      });
    }),
  );

  server.registerTool(
    'bulk_update_prices',
    {
      title: 'Cambiar precios en lote',
      description:
        'Cambia precios de varios productos, posiblemente en varias maquinas, en una sola operacion. ' +
        'Cada item necesita machineId, machineProductId y los precios nuevos en euros. ' +
        'Los items se procesan uno a uno y el resultado indica cuales han ido bien y cuales han fallado: ' +
        'un fallo no aborta el resto. ' +
        'POR DEFECTO SOLO SIMULA. Ejecute la simulacion, presente al usuario la lista completa de cambios ' +
        'con sus importes antes y despues, y solo aplique con dryRun=false tras confirmacion explicita. ' +
        'Maximo 200 items por llamada.' +
        dryRunNote,
      inputSchema: {
        items: z
          .array(
            z.object({
              machineId: z.number().int().positive(),
              machineProductId: machineProductIdSchema,
              prices: z.object({
                cash: z.number().nonnegative().optional(),
                card: z.number().nonnegative().optional(),
                prepaid: z.number().nonnegative().optional(),
                machine: z.number().nonnegative().optional(),
                retail: z.number().nonnegative().optional(),
              }),
            }),
          )
          .min(1)
          .max(200)
          .describe('Lista de cambios a aplicar'),
        dryRun: z.boolean().default(true).describe('true = solo simula (por defecto)'),
        confirmLargeChange: z.boolean().default(false),
      },
      annotations: { readOnlyHint: false, destructiveHint: true },
    },
    withErrorHandling(async (input) => {
      const result = await container.useCases.bulkUpdatePrices.execute({
        items: input.items,
        dryRun: forceDryRun ? true : input.dryRun,
        confirmLargeChange: input.confirmLargeChange,
        actor: MCP_ACTOR,
      });

      return asJson({
        ...result,
        message: input.dryRun && !forceDryRun
          ? 'Simulacion. Nada se ha modificado.'
          : `Aplicados ${result.succeeded} de ${result.total} cambios.`,
      });
    }),
  );
}
