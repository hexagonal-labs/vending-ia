import { DomainError } from '../../../domain/shared/errors.js';

export interface ToolResult {
  [key: string]: unknown;
  content: Array<{ [key: string]: unknown; type: 'text'; text: string }>;
  isError?: boolean;
}

/** Serializa la respuesta de forma compacta y legible para el modelo. */
export function asJson(payload: unknown): ToolResult {
  return {
    content: [{ type: 'text', text: JSON.stringify(payload, null, 2) }],
  };
}

/**
 * Envuelve el handler para que un error nunca tumbe la sesion MCP.
 *
 * Un agente sabe recuperarse de un error si se lo explicas: devolvemos el
 * codigo y el mensaje en texto plano, no una excepcion. Los errores de dominio
 * ya traen mensajes accionables ("repite con confirmacion explicita").
 */
export function withErrorHandling<TArgs extends Record<string, unknown>>(
  handler: (args: TArgs) => Promise<ToolResult>,
): (args: TArgs) => Promise<ToolResult> {
  return async (args: TArgs): Promise<ToolResult> => {
    try {
      return await handler(args);
    } catch (error) {
      const code = error instanceof DomainError ? error.code : 'UNEXPECTED_ERROR';
      const message = error instanceof Error ? error.message : String(error);

      return {
        isError: true,
        content: [{ type: 'text', text: JSON.stringify({ error: { code, message } }, null, 2) }],
      };
    }
  };
}
