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
  /** Faltantes según la telemetría MDB de la máquina. */
  readonly missing: number | null;
  readonly alertThreshold: number | null;
  /** La lógica de inventario usa exclusivamente MDB. */
  readonly source?: 'mdb' | null;
  readonly updatedAt?: string | null;
}

/** Un producto necesita reposición si el stock MDB llega al umbral configurado. */
export function needsRestock(product: MachineProduct): boolean {
  const { par, missing, alertThreshold } = product.stock;
  if (par === null || missing === null || alertThreshold === null) return false;
  const available = product.stock.available ?? Math.max(0, par - missing);
  return available <= alertThreshold;
}
