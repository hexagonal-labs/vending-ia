# Comandos Docker

Ejecutar desde `nayax-agents-langgraph`.

## Construir y arrancar

```bash
docker compose --env-file .env.docker up -d --build
```

## Ver estado

```bash
docker compose --env-file .env.docker ps
```

## Ver logs en directo

```bash
docker compose --env-file .env.docker logs -f
```

## Ver los últimos logs

```bash
docker compose --env-file .env.docker logs --tail=200
```

## Reconstruir después de cambios de código

```bash
docker compose --env-file .env.docker up -d --build
```

## Reconstrucción completa, sin caché

```bash
docker compose --env-file .env.docker build --no-cache
docker compose --env-file .env.docker up -d
```

## Reiniciar sin recompilar

```bash
docker compose --env-file .env.docker restart
```

## Recrear el contenedor sin recompilar

```bash
docker compose --env-file .env.docker up -d --force-recreate
```

## Detener el servicio

```bash
docker compose --env-file .env.docker down
```
