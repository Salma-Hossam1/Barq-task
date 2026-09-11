#!/usr/bin/env bash

set -euo pipefail

BACKUP_DIR="./backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/barq_tasks-${TIMESTAMP}.dump"

mkdir -p "$BACKUP_DIR"

if ! docker inspect --format '{{.State.Health.Status}}' postgres | grep -q '^healthy$'; then
    echo "ERROR: PostgreSQL is not healthy." >&2
    exit 1
fi

POSTGRES_USER="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' postgres | sed -n 's/^POSTGRES_USER=//p')"
POSTGRES_DB="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' postgres | sed -n 's/^POSTGRES_DB=//p')"
POSTGRES_PASSWORD="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' postgres | sed -n 's/^POSTGRES_PASSWORD=//p')"

if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" || -z "$POSTGRES_PASSWORD" ]]; then
    echo "ERROR: PostgreSQL credentials could not be read from the container." >&2
    exit 1
fi

echo "Creating PostgreSQL backup: $BACKUP_FILE"

docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    postgres \
    pg_dump \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --format=custom \
        --file="/tmp/barq_tasks.dump"

docker cp postgres:/tmp/barq_tasks.dump "$BACKUP_FILE"

docker exec postgres rm -f /tmp/barq_tasks.dump

echo "Backup created successfully: $BACKUP_FILE"