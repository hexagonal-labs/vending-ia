import { z } from 'zod';

/**
 * Esquemas compartidos entre HTTP y MCP.
 *
 * Se definen UNA vez y los usan las dos puertas de entrada. Asi es imposible
 * que la API REST acepte algo que el MCP rechaza, o al reves. Los tipos de
 * TypeScript salen inferidos de aqui, no duplicados a mano.
 */

export const priceKindSchema = z.enum(['cash', 'card', 'prepaid', 'machine', 'retail']);

export const isoDateSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/, 'La fecha debe tener formato YYYY-MM-DD');

export const machineIdSchema = z.coerce.number().int().positive();

export const priceMapSchema = z
  .object({
    cash: z.number().nonnegative().optional(),
    card: z.number().nonnegative().optional(),
    prepaid: z.number().nonnegative().optional(),
    machine: z.number().nonnegative().optional(),
    retail: z.number().nonnegative().optional(),
  })
  .refine((value) => Object.values(value).some((v) => v !== undefined), {
    message: 'Indica al menos un precio a cambiar',
  });

export const salesQuerySchema = z.object({
  from: isoDateSchema.optional(),
  to: isoDateSchema.optional(),
  machineId: machineIdSchema.optional(),
});

export const machineProductsParamsSchema = z.object({
  machineId: machineIdSchema,
});

export const machineProductsQuerySchema = z.object({
  onlyNeedingRestock: z
    .union([z.boolean(), z.string()])
    .optional()
    .transform((value) => value === true || value === 'true'),
});

/** Los IDs de producto de Lynx son opacos y pueden exceder la precision segura de JavaScript. */
export const machineProductIdSchema = z
  .union([
    z.string().regex(/^[1-9]\d*$/, 'machineProductId debe ser un entero positivo'),
    z.number().int().positive().safe(),
  ])
  .transform((value) => String(value));

export const updatePriceParamsSchema = z.object({
  machineId: machineIdSchema,
  machineProductId: machineProductIdSchema,
});

export const updatePriceBodySchema = z.object({
  prices: priceMapSchema,
  dryRun: z.boolean().default(true),
  confirmLargeChange: z.boolean().default(false),
});

export const bulkUpdateBodySchema = z.object({
  items: z
    .array(
      z.object({
        machineId: machineIdSchema,
        machineProductId: machineProductIdSchema,
        prices: priceMapSchema,
      }),
    )
    .min(1)
    .max(200),
  dryRun: z.boolean().default(true),
  confirmLargeChange: z.boolean().default(false),
});

export type PriceMapInput = z.infer<typeof priceMapSchema>;
export type SalesQueryInput = z.infer<typeof salesQuerySchema>;
