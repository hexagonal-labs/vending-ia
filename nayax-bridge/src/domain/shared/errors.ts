/**
 * Errores de dominio.
 *
 * Regla: el dominio NUNCA lanza errores de HTTP ni de Nayax. Lanza estos.
 * Los adaptadores (HTTP, MCP) son los que traducen `code` a un status o a un
 * mensaje util para el agente.
 */
export abstract class DomainError extends Error {
  abstract readonly code: string;

  constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

/** Los datos de entrada no cumplen una regla de negocio. */
export class ValidationError extends DomainError {
  readonly code = 'VALIDATION_ERROR';
}

/** El recurso pedido no existe. */
export class NotFoundError extends DomainError {
  readonly code = 'NOT_FOUND';

  constructor(resource: string, id: string | number) {
    super(`No se encontro ${resource} con id ${id}`);
  }
}

/** El cambio de precio supera el limite de seguridad configurado. */
export class PriceChangeTooLargeError extends DomainError {
  readonly code = 'PRICE_CHANGE_TOO_LARGE';

  constructor(
    readonly previous: number,
    readonly next: number,
    readonly ratio: number,
    readonly maxRatio: number,
  ) {
    super(
      `Cambio de precio de ${previous} a ${next} (${(ratio * 100).toFixed(1)}%) ` +
        `supera el maximo permitido del ${(maxRatio * 100).toFixed(0)}%. ` +
        `Repite la operacion con confirmacion explicita si es intencionado.`,
    );
  }
}

/** Las escrituras estan deshabilitadas por configuracion. */
export class WritesDisabledError extends DomainError {
  readonly code = 'WRITES_DISABLED';

  constructor() {
    super('Las operaciones de escritura estan deshabilitadas en esta instancia.');
  }
}

/** Quien llama no tiene permisos para esta operacion. */
export class ForbiddenError extends DomainError {
  readonly code = 'FORBIDDEN';
}

/**
 * Fallo al hablar con un sistema externo (Nayax).
 * Vive en el dominio para que los casos de uso puedan tratarlo sin conocer HTTP.
 */
export class IntegrationError extends DomainError {
  readonly code = 'INTEGRATION_ERROR';

  constructor(
    message: string,
    readonly upstreamStatus?: number,
    readonly upstreamBody?: unknown,
  ) {
    super(message);
  }
}
