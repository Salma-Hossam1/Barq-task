#!/usr/bin/env bash

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <backup-file>" >&2
    exit 1
fi

BACKUP_FILE="$1"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file does not exist: $BACKUP_FILE" >&2
    exit 1
fi

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

echo "Restoring PostgreSQL database from: $BACKUP_FILE"

docker cp "$BACKUP_FILE" postgres:/tmp/barq_tasks.restore.dump

docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    postgres \
    psql \
        --username="$POSTGRES_USER" \
        --dbname=postgres \
        --command="DROP DATABASE IF EXISTS \"$POSTGRES_DB\";"

docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    postgres \
    psql \
        --username="$POSTGRES_USER" \
        --dbname=postgres \
        --command="CREATE DATABASE \"$POSTGRES_DB\" OWNER \"$POSTGRES_USER\";"

docker exec \
    -e PGPASSWORD="$POSTGRES_PASSWORD" \
    postgres \
    pg_restore \
        --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" \
        --clean \
        --if-exists \
        /tmp/barq_tasks.restore.dump

docker exec postgres rm -f /tmp/barq_tasks.restore.dump

echo "PostgreSQL restore completed successfully."