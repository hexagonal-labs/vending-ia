# Pruebas de Nayax con Postman

Esta carpeta contiene una coleccion para probar:

- La API HTTP de `nayax-bridge` (`Bridge HTTP`).
- Las llamadas de lectura contra Nayax Lynx (`Nayax Lynx directo (solo lectura)`).

No se incluyen tokens reales. El entorno contiene solo valores de desarrollo y un
`nayaxToken` vacio.

## Importar

1. En Postman, selecciona **Import**.
2. Importa `nayax-bridge.postman_collection.json`.
3. Importa `nayax-bridge.local.postman_environment.json`.
4. Selecciona el entorno **Nayax Bridge - local**.

## Probar el bridge

Arranca primero el servidor HTTP:

```bash
npm run dev
```

Ejecuta en este orden:

1. `Bridge HTTP / Health`
2. `Bridge HTTP / List machines`
3. `Bridge HTTP / List machine products`
4. Las consultas de ventas o `Simulate price update`

La respuesta de `List machine products` guarda automáticamente el primer
`machineProductId` en el entorno. Se conserva como texto para no perder precisión
con identificadores Nayax de más de 15 dígitos.

Si el servidor usa otras API keys, actualiza `viewerApiKey` y `operatorApiKey`
en el entorno para que coincidan con `API_KEYS` del `.env` del bridge.

## Probar Nayax directamente

Para la carpeta `Nayax Lynx directo (solo lectura)`, configura en el entorno:

- `nayaxToken`: Bearer de Nayax Lynx.
- `nayaxOperatorId`: tu operador, necesario para `Sales widget`.
- `nayaxBaseUrl`: QA o producción.

Estas peticiones usan el mismo prefijo y las mismas rutas que el adaptador del
bridge. La colección incluye `Update machine product price (Nayax REAL)`, pero
está deshabilitada porque Nayax no ofrece `dryRun` en esta llamada: ejecutarla
modifica directamente `CreditCardPrice`. Para probar cambios de forma segura,
usa primero `Bridge HTTP / Simulate price update`; si necesitas ejecutar la
llamada directa, verifica el entorno y activa manualmente la petición.

También se incluye `Update machine products map (Nayax REAL)` para:

```http
PUT /operational/v1/machines/{MachineID}/machineProducts?avoidDelete=true
```

Esta petición recibe un array y actualiza el mapa de productos. Está
deshabilitada por defecto y contiene valores de ejemplo basados en una máquina
real; antes de activarla, reemplaza el body por el mapa actual que quieras
conservar. `avoidDelete=true` evita borrar productos que no estén incluidos en
la petición, según la documentación de Nayax.

## Usar un endpoint público

Puedes cambiar `bridgeBaseUrl` por la URL pública que realmente apunte al puerto
HTTP del bridge, por ejemplo:

```text
https://tu-dominio-publico.example
```

El endpoint público debe exponer `/health` y `/api/v1/*` del bridge. Si el puerto
8443 apunta a otro proceso, Postman podrá conectarse pero no estará probando
`nayax-bridge`.
