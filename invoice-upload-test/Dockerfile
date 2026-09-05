# syntax=docker/dockerfile:1.7

FROM python:3.12-slim

WORKDIR /opt/invoice-upload-test

COPY . .
COPY --from=invoice_bridge . /opt/invoice-bridge
COPY --from=pricing_catalog_bridge . /opt/pricing-catalog-bridge

# La interfaz llama a los bridges por MCP/STDIO. Se instalan en el mismo
# entorno Python, pero siguen siendo procesos y contratos independientes.
RUN pip install --no-cache-dir \
    -e . \
    -e /opt/invoice-bridge \
    -e /opt/pricing-catalog-bridge

ENV PYTHONUNBUFFERED=1 \
    INVOICE_BRIDGE_DIR=/opt/invoice-bridge \
    PRICING_CATALOG_BRIDGE_DIR=/opt/pricing-catalog-bridge \
    PRICING_DATA_DIR=/opt/invoice-upload-test/data/pricing \
    INVOICE_UPLOAD_DATA_DIR=/opt/invoice-upload-test/data \
    INVOICE_UPLOAD_HOST=0.0.0.0 \
    INVOICE_UPLOAD_PORT=8088

EXPOSE 8088

CMD ["invoice-upload-test"]
