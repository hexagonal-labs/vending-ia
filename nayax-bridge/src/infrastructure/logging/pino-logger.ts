import pino from 'pino';
import type { LoggerPort } from '../../application/ports/support.ports.js';

export function createLogger(level: string, pretty: boolean): LoggerPort & pino.Logger {
  const options = {
    level,
    // Nunca logueamos tokens ni cabeceras de autorizacion.
    redact: {
      paths: ['token', '*.token', 'headers.authorization', '*.headers.authorization', 'NAYAX_TOKEN'],
      censor: '[REDACTADO]',
    },
    ...(pretty
      ? { transport: { target: 'pino-pretty', options: { translateTime: 'HH:MM:ss', ignore: 'pid,hostname' } } }
      : {}),
  };

  // El transporte MCP usa stdout para JSON-RPC. Los logs estructurados deben
  // ir a stderr para no contaminar los mensajes del protocolo.
  return pretty ? pino(options) : pino(options, pino.destination(2));
}
