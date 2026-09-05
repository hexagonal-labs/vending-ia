import type { FastifyReply, FastifyRequest } from 'fastify';
import type { Actor } from '../../../application/ports/support.ports.js';
import type { AppConfig } from '../../../infrastructure/config/env.js';

declare module 'fastify' {
  interface FastifyRequest {
    actor?: Actor;
  }
}

/**
 * Autenticacion de NUESTRA API mediante API key.
 *
 * Importante: el token de Nayax nunca sale de este servidor. El frontend y los
 * agentes usan credenciales propias, con su rol. Si una se filtra, se revoca
 * sin tocar la integracion con Nayax.
 */
export function createAuthHook(config: AppConfig) {
  return async function authHook(request: FastifyRequest, reply: FastifyReply): Promise<void> {
    if (request.url === '/health') return;

    const header = request.headers['x-api-key'];
    const apiKey = Array.isArray(header) ? header[0] : header;

    if (!apiKey) {
      await reply.status(401).send({
        error: { code: 'UNAUTHORIZED', message: 'Falta la cabecera x-api-key' },
      });
      return;
    }

    const role = config.API_KEYS.get(apiKey);
    if (!role) {
      await reply.status(401).send({
        error: { code: 'UNAUTHORIZED', message: 'API key no valida' },
      });
      return;
    }

    request.actor = {
      id: `apikey:${apiKey.slice(0, 4)}***`,
      role,
      channel: 'http',
    };
  };
}
