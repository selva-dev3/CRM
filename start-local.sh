#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/eran-yeager/Downloads/Projects/CRM"
RUNTIME_ENV="/tmp/crm-backend-local.env"
RUNTIME_COMPOSE="/tmp/crm-compose-local.yml"

cd "$PROJECT_DIR"

sed 's/\$/$$/g' backend/.env > "$RUNTIME_ENV"

sed -i \
  -e 's#^CELERY_BROKER_URL=.*#CELERY_BROKER_URL=redis://redis:6379/0#' \
  -e 's#^CELERY_RESULT_BACKEND=.*#CELERY_RESULT_BACKEND=redis://redis:6379/0#' \
  -e 's#^REDIS_HOST=.*#REDIS_HOST=redis#' \
  -e 's#^REDIS_PORT=.*#REDIS_PORT=6379#' \
  "$RUNTIME_ENV"

sed \
  -e 's#\./backend/\.env#/tmp/crm-backend-local.env#g' \
  -e 's#context: ./backend#context: /home/eran-yeager/Downloads/Projects/CRM/backend#g' \
  -e 's#- ./backend:/app#- /home/eran-yeager/Downloads/Projects/CRM/backend:/app#g' \
  docker-compose.yml > "$RUNTIME_COMPOSE"

docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  up -d --build

docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  ps

for attempt in {1..30}; do
  if curl -fsS http://localhost:8000/health; then
    echo
    echo "CRM is running at http://localhost:3000"
    exit 0
  fi
  sleep 2
done

echo "Backend did not become healthy."
docker compose \
  --env-file "$RUNTIME_ENV" \
  -f "$RUNTIME_COMPOSE" \
  logs --tail=80 backend

exit 1
