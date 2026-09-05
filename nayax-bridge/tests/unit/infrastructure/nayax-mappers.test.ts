import { describe, expect, it } from 'vitest';
import { toCatalogProduct, toMachineProduct } from '../../../src/infrastructure/nayax/nayax.mappers.js';
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
});
