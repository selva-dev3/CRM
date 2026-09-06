#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/eran-yeager/Downloads/Projects/CRM"
SECRET_DIR="/home/eran-yeager/.config/crm"
UPSTASH_URL_FILE="$SECRET_DIR/upstash-redis-url"
RENDER_DB_URL_FILE="$SECRET_DIR/render-db-url"
RUNTIME_ENV="/tmp/crm-worker.env"
RUNTIME_COMPOSE="/tmp/crm-worker-compose.yml"

cd "$PROJECT_DIR"

if [[ ! -s "$UPSTASH_URL_FILE" || ! -s "$RENDER_DB_URL_FILE" ]]; then
  echo "Missing persistent CRM connection files in $SECRET_DIR."
  echo "Create them with chmod 600, then run this script again."
  exit 1
fi

upstash_url="$(<"$UPSTASH_URL_FILE")"
render_db_url="$(<"$RENDER_DB_URL_FILE")"

if [[ "$upstash_url" != rediss://* ]]; then
  echo "The Upstash URL must use rediss://."
  exit 1
fi

if [[ "$render_db_url" != postgresql://* && "$render_db_url" != postgres://* ]]; then
  echo "The Render database URL must use postgresql:// or postgres://."
  exit 1
fi

# Escape dollar signs from Render-style placeholders before Compose reads the file.
sed 's/\$/$$/g' backend/.env > "$RUNTIME_ENV"

set_env_value() {
  local key="$1"
  local value="$2"
  local escaped_value
  escaped_value="${value//\\/\\\\}"
  escaped_value="${escaped_value//&/\\&}"
  if grep -q "^${key}=" "$RUNTIME_ENV"; then
    sed -i "s#^${key}=.*#${key}=${escaped_value}#" "$RUNTIME_ENV"
  else
    printf '%s=%s\n' "$key" "$escaped_value" >> "$RUNTIME_ENV"
  fi
}

set_env_value DATABASE_URL "$render_db_url"
set_env_value CELERY_BROKER_URL "${upstash_url}?ssl_cert_reqs=CERT_REQUIRED"
set_env_value CELERY_RESULT_BACKEND "${upstash_url}?ssl_cert_reqs=CERT_REQUIRED"
set_env_value ENVIRONMENT production
set_env_value REDIS_HOST localhost
set_env_value REDIS_PORT 6379

# Worker/Beat must receive the env_file values directly. The regular Compose
# environment anchor intentionally points the development stack at local Redis.
sed \
  -e 's#context: ./backend#context: /home/eran-yeager/Downloads/Projects/CRM/backend#g' \
  -e 's#- ./backend:/app#- /home/eran-yeager/Downloads/Projects/CRM/backend:/app#g' \
  -e 's#- ./backend/\.env#- /tmp/crm-worker.env#g' \
  -e '/^[[:space:]]*environment: \*backend-runtime-environment$/d' \
  docker-compose.yml > "$RUNTIME_COMPOSE"

docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  config --quiet

echo "Starting the production-connected local Celery Worker and Beat..."
docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  up -d --no-deps --build --force-recreate celery_worker celery_beat

docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  ps celery_worker celery_beat

echo
echo "Worker logs:"
docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  logs --tail=30 celery_worker celery_beat
