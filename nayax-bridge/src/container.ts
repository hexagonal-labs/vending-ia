import { loadConfig, type AppConfig } from './infrastructure/config/env.js';
import { createLogger } from './infrastructure/logging/pino-logger.js';
import { InMemoryCache } from './infrastructure/cache/in-memory-cache.js';
import { FileAuditLog } from './infrastructure/persistence/file-audit-log.js';
import { SystemClock } from './infrastructure/system/system-clock.js';
import { NayaxHttpClient } from './infrastructure/nayax/nayax-http-client.js';
import { NayaxMachinesAdapter } from './infrastructure/nayax/nayax-machines.adapter.js';
import { NayaxMachineProductsAdapter } from './infrastructure/nayax/nayax-machine-products.adapter.js';
import { NayaxSalesAdapter } from './infrastructure/nayax/nayax-sales.adapter.js';
import { ListMachines } from './application/use-cases/machines/list-machines.use-case.js';
import { GetMachineProducts } from './application/use-cases/products/get-machine-products.use-case.js';
import { UpdateProductPrice } from './application/use-cases/products/update-product-price.use-case.js';
import { BulkUpdatePrices } from './application/use-cases/products/bulk-update-prices.use-case.js';
import { GetSalesSummary } from './application/use-cases/sales/get-sales-summary.use-case.js';
import { GetSalesByMachine } from './application/use-cases/sales/get-sales-by-machine.use-case.js';
import type { AuditLogPort, LoggerPort } from './application/ports/support.ports.js';

/**
 * Composicion de dependencias (composition root).
 *
 * Es el UNICO sitio donde se instancian clases concretas. Los casos de uso
 * reciben interfaces y no saben que hay detras: eso es la D de SOLID.
 * Para tests, se construye un contenedor equivalente con dobles.
 */
export interface Container {
  readonly config: AppConfig;
  readonly logger: LoggerPort;
  readonly audit: AuditLogPort;
  readonly useCases: {
    listMachines: ListMachines;
    getMachineProducts: GetMachineProducts;
    updateProductPrice: UpdateProductPrice;
    bulkUpdatePrices: BulkUpdatePrices;
    getSalesSummary: GetSalesSummary;
    getSalesByMachine: GetSalesByMachine;
  };
}

export interface BuildContainerOptions {
  /** El servidor MCP habla por stdout: los logs deben ir a stderr, sin colores. */
  readonly quietLogs?: boolean;
}

export function buildContainer(options: BuildContainerOptions = {}): Container {
  const config = loadConfig();

  const logger = createLogger(
    config.LOG_LEVEL,
    config.NODE_ENV === 'development' && !options.quietLogs,
  );

  const clock = new SystemClock();
  const cache = new InMemoryCache(config.CACHE_TTL_SECONDS);
  const audit = new FileAuditLog('data/audit.log.jsonl');

  const http = new NayaxHttpClient(
    {
      baseUrl: config.NAYAX_BASE_URL,
      apiPrefix: config.NAYAX_API_PREFIX,
      token: config.NAYAX_TOKEN,
      timeoutMs: config.NAYAX_TIMEOUT_MS,
      maxRetries: config.NAYAX_MAX_RETRIES,
    },
    logger,
  );

  const machinesAdapter = new NayaxMachinesAdapter(http);
  const productsAdapter = new NayaxMachineProductsAdapter(http);
  const salesAdapter = new NayaxSalesAdapter(http, { operatorId: config.NAYAX_OPERATOR_ID });

  const updateProductPrice = new UpdateProductPrice(
    productsAdapter,
    productsAdapter,
    audit,
    cache,
    clock,
    logger,
    {
      writesEnabled: config.WRITES_ENABLED,
      maxPriceVariation: config.MAX_PRICE_CHANGE_RATIO,
    },
  );

  return {
    config,
    logger,
    audit,
    useCases: {
      listMachines: new ListMachines(machinesAdapter, cache),
      getMachineProducts: new GetMachineProducts(productsAdapter, cache),
      updateProductPrice,
      bulkUpdatePrices: new BulkUpdatePrices(updateProductPrice),
      getSalesSummary: new GetSalesSummary(salesAdapter, clock),
      getSalesByMachine: new GetSalesByMachine(salesAdapter, clock),
    },
  };
}
