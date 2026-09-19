import { Money } from '../../domain/shared/money.js';
import { machineId, machineProductId, nayaxProductId } from '../../domain/shared/ids.js';
import { Pricing, type PriceKind } from '../../domain/product/pricing.js';
import type { CatalogProduct, MachineProduct } from '../../domain/product/machine-product.js';
import type { Machine, MachineStatus } from '../../domain/machine/machine.js';
import type { NayaxMachineDto, NayaxMachineProductDto, NayaxProductDto } from './nayax.dto.js';

/**
 * Traduccion entre el vocabulario de Nayax y el nuestro.
 *
 * Concentrar el mapeo aqui significa que si Nayax renombra un campo, se toca
 * un solo fichero. El dominio ni se entera.
 */

/** Nuestro PriceKind -> nombre del campo en Lynx. */
export const PRICE_FIELD_BY_KIND: Record<PriceKind, keyof NayaxMachineProductDto> = {
  cash: 'CashPrice',
  card: 'CreditCardPrice',
  prepaid: 'PrePaidCardPrice',
  machine: 'MachinePrice',
  retail: 'RetailPrice',
};

export function toMachineProduct(
  dto: NayaxMachineProductDto,
  catalogProduct: CatalogProduct | null = null,
): MachineProduct {
  const rawMachineProductId = dto.MachineProductID ?? 0;
  const rawMachineId = dto.MachineID ?? 0;
  const stock = selectStockReading(dto);

  return {
    machineProductId: machineProductId(rawMachineProductId),
    machineId: machineId(rawMachineId),
    nayaxProductId: dto.NayaxProductID ? nayaxProductId(dto.NayaxProductID) : null,
    catalogProduct,
    name:
      catalogProduct?.productName?.trim() ||
      dto.DEXProductName?.trim() ||
      catalogProduct?.dexProductName?.trim() ||
      `Producto ${rawMachineProductId}`,
    selectionCode: dto.PACode ?? dto.OperatorButtonCode ?? null,
    pricing: Pricing.fromDecimals({
      cash: dto.CashPrice,
      card: dto.CreditCardPrice,
      prepaid: dto.PrePaidCardPrice,
      machine: dto.MachinePrice,
      retail: dto.RetailPrice,
    }),
    stock: {
      par: dto.PAR ?? null,
      available: availableStock(dto.PAR, stock.missing),
      missing: stock.missing,
      alertThreshold: dto.VendOutAlertThreshold ?? null,
      source: stock.source,
      updatedAt: stock.updatedAt,
      readings: {
        dex: {
          missing: dto.MissingStockByDEX ?? null,
          updatedAt: dto.DEXMissingStockLastUpdated ?? null,
        },
        mdb: {
          missing: dto.MissingStockByMDB ?? null,
          updatedAt: dto.MDBMissingStockLastUpdated ?? null,
        },
      },
    },
    lastSaleAt: dto.last_sale_dt ?? null,
    slowMover: dto.slow_mover ?? false,
  };
}

type StockSource = 'dex' | 'mdb';

interface SelectedStockReading {
  readonly source: StockSource | null;
  readonly missing: number | null;
  readonly updatedAt: string | null;
}

/**
 * Nayax puede devolver dos lecturas de faltantes: DEX y MDB. No se debe elegir
 * una por su mera presencia (0 también es un valor): usamos la lectura con
 * fecha válida más reciente. Cuando faltan las fechas o empatan, MDB gana por
 * ser la señal directa del bus de la máquina.
 */
function selectStockReading(dto: NayaxMachineProductDto): SelectedStockReading {
  const candidates: Array<SelectedStockReading & { readonly timestamp: number | null }> = [
    {
      source: 'mdb' as const,
      missing: dto.MissingStockByMDB ?? null,
      updatedAt: dto.MDBMissingStockLastUpdated ?? null,
      timestamp: timestampOf(dto.MDBMissingStockLastUpdated),
    },
    {
      source: 'dex' as const,
      missing: dto.MissingStockByDEX ?? null,
      updatedAt: dto.DEXMissingStockLastUpdated ?? null,
      timestamp: timestampOf(dto.DEXMissingStockLastUpdated),
    },
  ].filter((candidate) => candidate.missing !== null);

  if (candidates.length === 0) return { source: null, missing: null, updatedAt: null };

  candidates.sort((left, right) => {
    if (left.timestamp === null && right.timestamp === null) return 0;
    if (left.timestamp === null) return 1;
    if (right.timestamp === null) return -1;
    return right.timestamp - left.timestamp;
  });

  const selected = candidates[0]!;
  return {
    source: selected.source,
    missing: selected.missing,
    updatedAt: selected.updatedAt,
  };
}

function timestampOf(value: string | null | undefined): number | null {
  if (!value) return null;
  const timestamp = Date.parse(value);
  return Number.isNaN(timestamp) ? null : timestamp;
}

function availableStock(par: number | null | undefined, missing: number | null): number | null {
  if (par === null || par === undefined || missing === null) return null;
  return Math.max(0, par - missing);
}

export function toCatalogProduct(dto: NayaxProductDto): CatalogProduct {
  return {
    nayaxProductId: dto.NayaxProductID ? nayaxProductId(dto.NayaxProductID) : null,
    productGroupId: dto.ProductGroupID ?? null,
    actorId: dto.ActorID ?? null,
    productManufacturerId: dto.ProductManufacturerID ?? null,
    productName: dto.ProductName ?? null,
    productCatalogNumber: dto.ProductCatalogNumber ?? null,
    productBarcode: dto.ProductBarcode ?? null,
    productPackageQuantity: dto.ProductPackageQuantity ?? null,
    productDescription: dto.ProductDescription ?? null,
    productVolumeTypeId: dto.ProductVolumeTypeID ?? null,
    dexProductName: dto.DEXProductName ?? null,
    productCostPrice: dto.ProductCostPrice ?? null,
    productDefaultRetailPrice: dto.ProductDefaultRetailPrice ?? null,
    productMinimumPickQty: dto.ProductMinimumPickQTY ?? null,
    productStatus: dto.ProductStatus ?? null,
    productCashPrice: dto.ProductCashPrice ?? null,
    productCreditCardPrice: dto.ProductCreditCardPrice ?? null,
    productPrepaidCardPrice: dto.ProductPrepaidCardPrice ?? null,
    productExternalPrepaidCardPrice: dto.ProductExternalPrepaidCardPrice ?? null,
    productMemberTypePriceBit: dto.ProductMemberTypePriceBit ?? null,
    productPictureUrl: dto.ProductPictureURL ?? null,
    caloriesPer100g: dto.CaloriesPer100g ?? null,
    caloriesPerServing: dto.CaloriesPerServing ?? null,
    eanCode: dto.EANCode ?? null,
    productCreatedBy: dto.ProductCreatedBy ?? null,
    productCreationDate: dto.ProductCreationDate ?? null,
    productUpdatedBy: dto.ProductUpdatedBy ?? null,
    productLastUpdated: dto.ProductLastUpdated ?? null,
    vatId: dto.VatId ?? null,
    sequenceNumber: dto.SequenceNumber ?? null,
    ageVerificationEnableBit: dto.AgeVerificationEnableBit ?? null,
    depositTypeId: dto.DepositTypeID ?? null,
    depositFee: dto.DepositFee ?? null,
    depositTax: dto.DepositTax ?? null,
    refs: dto.Refs ?? null,
  };
}

/** Convierte nuestros precios (euros) al cuerpo que espera Lynx. */
export function toPriceUpdateBody(
  prices: Partial<Record<PriceKind, number>>,
): Record<string, number> {
  const body: Record<string, number> = {};
  for (const [kind, value] of Object.entries(prices)) {
    if (value === undefined) continue;
    const field = PRICE_FIELD_BY_KIND[kind as PriceKind];
    body[field as string] = Number(value.toFixed(2));
  }
  return body;
}

export function toMachine(dto: NayaxMachineDto): Machine {
  return {
    machineId: machineId(dto.MachineID ?? 0),
    name: dto.MachineName?.trim() || `Maquina ${dto.MachineID ?? '?'}`,
    siteName: dto.SiteName ?? null,
    status: toMachineStatus(dto.MachineStatus),
    lastSeenAt: dto.LastSeen ?? null,
  };
}

function toMachineStatus(raw: string | number | null | undefined): MachineStatus {
  if (raw === null || raw === undefined) return 'unknown';
  const normalized = String(raw).toLowerCase();
  if (normalized === '1' || normalized === 'online' || normalized === 'active') return 'online';
  if (normalized === '0' || normalized === 'offline') return 'offline';
  return 'unknown';
}

export function toMoney(value: number | null | undefined): Money {
  return Money.fromDecimal(value ?? 0);
}
