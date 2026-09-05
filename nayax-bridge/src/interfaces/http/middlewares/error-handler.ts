import type { FastifyError, FastifyReply, FastifyRequest } from 'fastify';
import { ZodError } from 'zod';
import {
  DomainError,
  ForbiddenError,
  IntegrationError,
  NotFoundError,
  PriceChangeTooLargeError,
  ValidationError,
  WritesDisabledError,
} from '../../../domain/shared/errors.js';
import type { LoggerPort } from '../../../application/ports/support.ports.js';

/**
 * Traduce errores de dominio a HTTP.
 *
 * Este es el UNICO sitio donde el dominio se convierte en status codes. Un
 * error crudo de Nayax nunca llega al cliente.
 */
const STATUS_BY_ERROR = new Map<string, number>([
  [ValidationError.name, 400],
  [PriceChangeTooLargeError.name, 409],
  [WritesDisabledError.name, 403],
  [ForbiddenError.name, 403],
  [NotFoundError.name, 404],
  [IntegrationError.name, 502],
]);

export function createErrorHandler(logger: LoggerPort) {
  return function errorHandler(
    error: FastifyError | Error,
    request: FastifyRequest,
    reply: FastifyReply,
  ): void {
    if (error instanceof ZodError) {
      void reply.status(400).send({
        error: {
          code: 'VALIDATION_ERROR',
          message: 'Datos de entrada no validos',
          details: error.issues.map((issue) => ({
            path: issue.path.join('.'),
            message: issue.message,
          })),
        },
      });
      return;
    }

    if (error instanceof DomainError) {
      const status = STATUS_BY_ERROR.get(error.name) ?? 400;

      if (status >= 500) {
        logger.error({ err: error, url: request.url }, 'Error de integracion');
      }

      void reply.status(status).send({
        error: { code: error.code, message: error.message },
      });
      return;
    }

    logger.error({ err: error, url: request.url }, 'Error no controlado');
    void reply.status(500).send({
      error: { code: 'INTERNAL_ERROR', message: 'Error interno del servidor' },
    });
  };
}
