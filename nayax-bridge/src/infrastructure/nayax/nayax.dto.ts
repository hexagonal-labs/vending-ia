/**
 * Formas crudas que devuelve Lynx.
 *
 * Solo se declaran los campos que usamos. Lynx devuelve objetos con 30+ campos
 * y no tiene sentido arrastrarlos todos hasta el dominio.
 *
 * IMPORTANTE: estos tipos son una foto de la documentacion, no un contrato
 * garantizado. Verifica los nombres exactos con el conector MCP de Nayax
 * (`devzone.nayax.com/mcp`) antes de dar por buena una integracion.
 */

export interface NayaxMachineProductDto {
  /** Lynx puede devolver este identificador como string y superar MAX_SAFE_INTEGER. */
  MachineProductID?: string | number | null;
  NayaxProductID?: number | null;
  MachineID?: number | null;
  MDBCode?: number | null;
  PAR?: number | null;
  CashPrice?: number | null;
  CreditCardPrice?: number | null;
  MachinePrice?: number | null;
  RetailPrice?: number | null;
  PrePaidCardPrice?: number | null;
  DEXProductName?: string | null;
  PACode?: string | null;
  ProductMinimumPickQTY?: number | null;
  VendOutAlertThreshold?: number | null;
  MissingStockByDEX?: number | null;
  DEXMissingStockLastUpdated?: string | null;
  MissingStockByMDB?: number | null;
  MDBMissingStockLastUpdated?: string | null;
  OperatorButtonCode?: string | null;
  last_sale_dt?: string | null;
  slow_mover?: boolean | null;
  ProductRef?: string | null;
}

/** Respuesta de GET /products/{NayaxProductID}. */
export interface NayaxProductDto {
  NayaxProductID?: number | null;
  ProductGroupID?: number | null;
  ActorID?: number | null;
  ProductManufacturerID?: number | null;
  ProductName?: string | null;
  ProductCatalogNumber?: string | null;
  ProductBarcode?: string | null;
  ProductPackageQuantity?: number | null;
  ProductDescription?: string | null;
  ProductVolumeTypeID?: number | null;
  DEXProductName?: string | null;
  ProductCostPrice?: number | null;
  ProductDefaultRetailPrice?: number | null;
  ProductMinimumPickQTY?: number | null;
  ProductStatus?: number | null;
  ProductCashPrice?: number | null;
  ProductCreditCardPrice?: number | null;
  ProductPrepaidCardPrice?: number | null;
  ProductExternalPrepaidCardPrice?: number | null;
  ProductMemberTypePriceBit?: boolean | null;
  ProductPictureURL?: string | null;
  CaloriesPer100g?: number | null;
  CaloriesPerServing?: number | null;
  EANCode?: string | null;
  ProductCreatedBy?: number | null;
  ProductCreationDate?: string | null;
  ProductUpdatedBy?: number | null;
  ProductLastUpdated?: string | null;
  VatId?: number | null;
  SequenceNumber?: number | null;
  AgeVerificationEnableBit?: boolean | null;
  DepositTypeID?: number | null;
  DepositFee?: number | null;
  DepositTax?: number | null;
  Refs?: Record<string, string | null> | null;
}

export interface NayaxMachineDto {
  MachineID?: number | null;
  MachineName?: string | null;
  SiteName?: string | null;
  MachineStatus?: string | number | null;
  LastSeen?: string | null;
}

export interface NayaxWidgetDataDto {
  Data?: unknown;
  data?: unknown;
  [key: string]: unknown;
}
