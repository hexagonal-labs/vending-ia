# syntax=docker/dockerfile:1.7

# El proyecto usa el servidor MCP del bridge por STDIO. Por eso la imagen
# conjunta contiene Python, Node.js y el nayax-bridge compilado.
FROM node:20-bookworm-slim AS bridge-build

WORKDIR /opt/src/nayax-bridge
COPY --from=bridge . .
RUN npm ci \
    && npm run build \
    && npm prune --omit=dev

FROM ghcr.io/astral-sh/uv:0.12.5 AS uv

FROM node:20-bookworm-slim AS node-runtime

FROM python:3.12-slim AS runtime

COPY --from=uv /uv /uvx /bin/
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    NAYAX_BRIDGE_DIR=/opt/nayax-bridge \
    SUPPLIER_BRIDGE_DIR=/opt/supplier-bridge \
    PRICING_CATALOG_BRIDGE_DIR=/opt/pricing-catalog-bridge \
    INVOICE_BRIDGE_DIR=/opt/invoice-bridge \
    PRICING_DATA_DIR=/opt/nayax-agents-langgraph/data/pricing \
    PRICING_EXPORT_DIR=/opt/nayax-agents-langgraph/reports \
    NAYAX_NODE_COMMAND=node \
    NAYAX_CHECKPOINT_DB=/opt/nayax-agents-langgraph/data/checkpoints.db

WORKDIR /opt/nayax-agents-langgraph

# Instala primero las dependencias para aprovechar la cache de Docker.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --extra studio --no-dev --no-install-project

COPY src ./src
COPY config ./config
COPY langgraph.json README.md ./
RUN uv sync --frozen --extra studio --no-dev

COPY --from=bridge-build /opt/src/nayax-bridge /opt/nayax-bridge
COPY --from=supplier_bridge . /opt/supplier-bridge
COPY --from=pricing_catalog_bridge . /opt/pricing-catalog-bridge
COPY --from=invoice_bridge . /opt/invoice-bridge
RUN uv pip install --python .venv/bin/python rapidfuzz pypdf \
    && mkdir -p /opt/nayax-agents-langgraph/data
ENV PYTHONPATH=/opt/supplier-bridge/src:/opt/pricing-catalog-bridge/src:/opt/invoice-bridge/src
RUN node --version

EXPOSE 2024

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:2024/docs', timeout=3)"

CMD ["uv", "run", "langgraph", "dev", "--host", "0.0.0.0", "--port", "2024", "--no-browser"]
