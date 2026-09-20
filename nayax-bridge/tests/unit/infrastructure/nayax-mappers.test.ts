import { describe, expect, it } from 'vitest';
import { toCatalogProduct, toMachineProduct } from '../../../src/infrastructure/nayax/nayax.mappers.js';
import { needsRestock } from '../../../src/domain/product/machine-product.js';
import { machineProductIdSchema } from '../../../src/shared/schemas.js';

const LARGE_MACHINE_PRODUCT_ID = '62815040066753839';

describe('identificadores de productos Nayax', () => {
  it('conserva exactamente un MachineProductID grande devuelto como string', () => {
    const product = toMachineProduct({
      MachineProductID: LARGE_MACHINE_PRODUCT_ID,
      MachineID: 236561482,
      DEXProductName: 'Producto real',
    });

    expect(product.machineProductId).toBe(LARGE_MACHINE_PRODUCT_ID);
  });

  it('acepta el identificador grande en los inputs de escritura', () => {
    expect(machineProductIdSchema.parse(LARGE_MACHINE_PRODUCT_ID)).toBe(LARGE_MACHINE_PRODUCT_ID);
  });

  it('prioriza ProductName del catalogo sobre el nombre DEX de la maquina', () => {
    const catalog = toCatalogProduct({
      NayaxProductID: 243115947215801,
      ProductName: 'Nombre real de catalogo',
      ProductDescription: 'Descripcion completa',
      ProductPictureURL: 'https://example.test/product.jpg',
    });
    const product = toMachineProduct(
      {
        MachineProductID: LARGE_MACHINE_PRODUCT_ID,
        MachineID: 236561482,
        DEXProductName: 'Nombre DEX incompleto',
      },
      catalog,
    );

    expect(product.name).toBe('Nombre real de catalogo');
    expect(product.catalogProduct).toMatchObject({
      productName: 'Nombre real de catalogo',
      productDescription: 'Descripcion completa',
      productPictureUrl: 'https://example.test/product.jpg',
    });
  });

  it('usa exclusivamente MDB para calcular el stock, aunque DEX sea más reciente', () => {
    const product = toMachineProduct({
      MachineProductID: '178561114546281',
      MachineID: 236561482,
      PAR: 8,
      MissingStockByDEX: 0,
      DEXMissingStockLastUpdated: '2030-01-10T18:02:39.053',
      MissingStockByMDB: 1,
      MDBMissingStockLastUpdated: '2026-09-18T23:34:53.723',
      VendOutAlertThreshold: 7,
    });

    expect(product.stock).toMatchObject({
      par: 8,
      available: 7,
      missing: 1,
      source: 'mdb',
      updatedAt: '2026-09-18T23:34:53.723',
    });
    expect(needsRestock(product)).toBe(true);
  });

  it('marca reposición solo al llegar al umbral MDB configurado', () => {
    const product = toMachineProduct({
      MachineProductID: '2',
      MachineID: 5001,
      PAR: 8,
      MissingStockByDEX: 0,
      MissingStockByMDB: 2,
      VendOutAlertThreshold: 6,
    });

    expect(product.stock).toMatchObject({ available: 6, missing: 2, source: 'mdb' });
    expect(needsRestock(product)).toBe(true);
  });
});
