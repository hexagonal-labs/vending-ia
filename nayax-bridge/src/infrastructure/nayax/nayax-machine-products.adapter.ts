import type { MachineProductsPort, PriceWriterPort } from '../../application/ports/nayax.ports.js';
import type { MachineId, MachineProductId } from '../../domain/shared/ids.js';
import type { CatalogProduct, MachineProduct } from '../../domain/product/machine-product.js';
import type { PriceKind } from '../../domain/product/pricing.js';
import type { NayaxHttpClient } from './nayax-http-client.js';
import type { NayaxMachineProductDto, NayaxProductDto } from './nayax.dto.js';
import { toCatalogProduct, toMachineProduct, toPriceUpdateBody } from './nayax.mappers.js';

const PRODUCT_DETAILS_CONCURRENCY = 8;

/**
 * Adaptador de productos de maquina sobre Lynx.
 *
 * Implementa dos puertos porque comparten el mismo recurso remoto, pero los
 * casos de uso solo dependen del que necesitan: los de lectura reciben
 * MachineProductsPort y nunca ven updatePrices.
 *
 * Endpoints usados (verificar contra la doc con el conector MCP de Nayax):
 *   GET /machines/{machineId}/machineProducts
 *   GET /products/{nayaxProductId}
 *   GET /machines/{machineId}/machineProducts/{machineProductId}
 *   PUT /machines/{machineId}/machineProducts/{machineProductId}
 */
export class NayaxMachineProductsAdapter implements MachineProductsPort, PriceWriterPort {
  constructor(private readonly http: NayaxHttpClient) {}

  async listByMachine(machineId: MachineId): Promise<MachineProduct[]> {
    const response = await this.http.request<NayaxMachineProductDto[]>({
      method: 'GET',
      path: `/machines/${machineId}/machineProducts`,
    });

    const machineProducts = (response ?? []).filter(hasIds);
    const catalogProducts = await this.getCatalogProducts(machineProducts);

    return machineProducts.map((product) => {
      const productId = productIdFromMachineProduct(product);
      return toMachineProduct(product, productId ? catalogProducts.get(productId) ?? null : null);
    });
  }

  async getById(
    machineId: MachineId,
    productId: MachineProductId,
  ): Promise<MachineProduct | null> {
    const response = await this.http.request<NayaxMachineProductDto | null>({
      method: 'GET',
      path: `/machines/${machineId}/machineProducts/${productId}`,
    });

    if (!response || !hasIds(response)) return null;
    return toMachineProduct(response);
  }

  async updatePrices(
    machineId: MachineId,
    productId: MachineProductId,
    prices: Partial<Record<PriceKind, number>>,
  ): Promise<MachineProduct> {
    const response = await this.http.request<NayaxMachineProductDto>({
      method: 'PUT',
      path: `/machines/${machineId}/machineProducts/${productId}`,
      body: {
        MachineProductID: productId,
        MachineID: machineId,
        ...toPriceUpdateBody(prices),
      },
    });

    return toMachineProduct({
      ...response,
      MachineID: response?.MachineID ?? machineId,
      MachineProductID: response?.MachineProductID ?? productId,
    });
  }

  /**
   * Recupera cada producto maestro una sola vez, aunque este presente en varias
   * selecciones de la misma maquina. Un fallo puntual no oculta el resto del
   * mapa de maquina: esa fila conserva sus datos locales y catalogProduct=null.
   */
  private async getCatalogProducts(
    machineProducts: NayaxMachineProductDto[],
  ): Promise<Map<number, CatalogProduct>> {
    const productIds = [
      ...new Set(
        machineProducts
          .map(productIdFromMachineProduct)
          .filter((id): id is number => id !== null),
      ),
    ];
    const detailsById = new Map<number, CatalogProduct>();

    await forEachWithConcurrency(productIds, PRODUCT_DETAILS_CONCURRENCY, async (productId) => {
      try {
        const response = await this.http.request<NayaxProductDto | null>({
          method: 'GET',
          path: `/products/${productId}`,
        });
        if (response) detailsById.set(productId, toCatalogProduct(response));
      } catch {
        // Una ficha borrada o inaccesible no debe hacer fallar el inventario entero.
        // El cliente HTTP ya registra URL, estado y reintentos de cada llamada.
      }
    });

    return detailsById;
  }
}

/** Lynx a veces devuelve filas incompletas; las descartamos antes de mapear. */
function hasIds(dto: NayaxMachineProductDto): boolean {
  return Boolean(dto.MachineProductID && dto.MachineID);
}

/** Preferimos el id explicito; ProductRef cubre las respuestas que no lo traen. */
function productIdFromMachineProduct(dto: NayaxMachineProductDto): number | null {
  if (isPositiveInteger(dto.NayaxProductID)) return dto.NayaxProductID;

  const match = dto.ProductRef?.match(/(?:^|\/)products\/(\d+)\/?$/i);
  if (!match) return null;

  const id = Number(match[1]);
  return isPositiveInteger(id) ? id : null;
}

function isPositiveInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}

async function forEachWithConcurrency<T>(
  items: readonly T[],
  concurrency: number,
  fn: (item: T) => Promise<void>,
): Promise<void> {
  let nextIndex = 0;
  const worker = async (): Promise<void> => {
    while (nextIndex < items.length) {
      const index = nextIndex++;
      const item = items[index];
      if (item !== undefined) await fn(item);
    }
  };

  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, worker));
}
