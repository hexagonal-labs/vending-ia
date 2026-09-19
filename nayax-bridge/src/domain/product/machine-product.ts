import type { MachineId, MachineProductId, NayaxProductId } from '../shared/ids.js';
import type { Pricing } from './pricing.js';

/**
 * Un producto tal y como esta mapeado en una maquina concreta.
 * Es la entidad sobre la que se cambian precios.
 */
export interface MachineProduct {
  readonly machineProductId: MachineProductId;
  readonly machineId: MachineId;
  readonly nayaxProductId: NayaxProductId | null;
  /** Ficha global de catalogo, obtenida de GET /products/{NayaxProductID}. */
  readonly catalogProduct: CatalogProduct | null;
  readonly name: string;
  /** Codigo de seleccion visible en la maquina (A1, B2...). */
  readonly selectionCode: string | null;
  readonly pricing: Pricing;
  readonly stock: StockInfo;
  readonly lastSaleAt: string | null;
  readonly slowMover: boolean;
}

/**
 * Producto maestro de Nayax. Los importes y el stock de MachineProduct siguen
 * siendo los valores concretos de la seleccion dentro de una maquina.
 */
export interface CatalogProduct {
  readonly nayaxProductId: NayaxProductId | null;
  readonly productGroupId: number | null;
  readonly actorId: number | null;
  readonly productManufacturerId: number | null;
  readonly productName: string | null;
  readonly productCatalogNumber: string | null;
  readonly productBarcode: string | null;
  readonly productPackageQuantity: number | null;
  readonly productDescription: string | null;
  readonly productVolumeTypeId: number | null;
  readonly dexProductName: string | null;
  readonly productCostPrice: number | null;
  readonly productDefaultRetailPrice: number | null;
  readonly productMinimumPickQty: number | null;
  readonly productStatus: number | null;
  readonly productCashPrice: number | null;
  readonly productCreditCardPrice: number | null;
  readonly productPrepaidCardPrice: number | null;
  readonly productExternalPrepaidCardPrice: number | null;
  readonly productMemberTypePriceBit: boolean | null;
  readonly productPictureUrl: string | null;
  readonly caloriesPer100g: number | null;
  readonly caloriesPerServing: number | null;
  readonly eanCode: string | null;
  readonly productCreatedBy: number | null;
  readonly productCreationDate: string | null;
  readonly productUpdatedBy: number | null;
  readonly productLastUpdated: string | null;
  readonly vatId: number | null;
  readonly sequenceNumber: number | null;
  readonly ageVerificationEnableBit: boolean | null;
  readonly depositTypeId: number | null;
  readonly depositFee: number | null;
  readonly depositTax: number | null;
  readonly refs: Record<string, string | null> | null;
}

export interface StockInfo {
  /** Nivel objetivo de reposicion. */
  readonly par: number | null;
  /** Unidades disponibles estimadas: PAR - missing. */
  readonly available?: number | null;
  /** Faltantes de la fuente de telemetría seleccionada. */
  readonly missing: number | null;
  readonly alertThreshold: number | null;
  /** Fuente elegida por tener la lectura más reciente; MDB gana si no hay fecha. */
  readonly source?: 'dex' | 'mdb' | null;
  readonly updatedAt?: string | null;
  /** Lecturas originales, expuestas para poder auditar discrepancias de Nayax. */
  readonly readings?: {
    readonly dex: StockReading;
    readonly mdb: StockReading;
  };
}

export interface StockReading {
  readonly missing: number | null;
  readonly updatedAt: string | null;
}

/** Un producto necesita reposición cuando la telemetría indica alguna unidad faltante.
 *
 * El umbral de alerta es una configuración opcional de Nayax; no tenerlo no
 * convierte una selección parcialmente vacía en una selección llena.
 */
export function needsRestock(product: MachineProduct): boolean {
  return (product.stock.missing ?? 0) > 0;
}
