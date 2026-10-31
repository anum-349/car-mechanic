#!/usr/bin/env sh
set -eu

backup_uri=${1:-}
: "${backup_uri:?Usage: RESTORE_CONFIRM=YES RESTORE_TARGET_DB=... sh scripts/restore.sh s3://bucket/key.dump}"
: "${RESTORE_CONFIRM:?Set RESTORE_CONFIRM=YES after reviewing the target database}"
: "${RESTORE_TARGET_DB:?Set RESTORE_TARGET_DB to a new database name}"
[ "$RESTORE_CONFIRM" = YES ] || { echo "Restore cancelled; RESTORE_CONFIRM must equal YES." >&2; exit 2; }
case "$RESTORE_TARGET_DB" in
    ''|[!A-Za-z_]*|*[!A-Za-z0-9_]*)
        echo "RESTORE_TARGET_DB must be a PostgreSQL identifier using letters, digits, and underscores." >&2
        exit 2
        ;;
esac
[ "${#RESTORE_TARGET_DB}" -le 63 ] || { echo "RESTORE_TARGET_DB is too long." >&2; exit 2; }

compose_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_env=${COMPOSE_ENV_FILE:-$compose_root/.env.production}
[ -f "$compose_env" ] || compose_env=$compose_root/.env
[ -f "$compose_env" ] || { echo "Set COMPOSE_ENV_FILE to the Compose environment file." >&2; exit 2; }
tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT HUP INT TERM
chmod 600 "$tmp_file"

set --
[ -z "${S3_ENDPOINT_URL:-}" ] || set -- --endpoint-url "$S3_ENDPOINT_URL"
[ -z "${AWS_DEFAULT_REGION:-}" ] || set -- "$@" --region "$AWS_DEFAULT_REGION"
aws s3 cp "$backup_uri" "$tmp_file" --only-show-errors "$@"
test -s "$tmp_file"

echo "Creating a new restore target database."
primary_db=$(docker compose --env-file "$compose_env" \
    -f "$compose_root/docker-compose.yml" exec -T db printenv POSTGRES_DB | tr -d '\r\n')
[ "$RESTORE_TARGET_DB" != "$primary_db" ] || {
    echo "Restore target must differ from the live database; restores never overwrite it." >&2
    exit 2
}
docker compose --env-file "$compose_env" -f "$compose_root/docker-compose.yml" \
    exec -T db sh -ec \
    'export PGPASSWORD="$POSTGRES_PASSWORD"; psql -h 127.0.0.1 -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$1\""' \
    sh "$RESTORE_TARGET_DB"

echo "Restoring backup into $RESTORE_TARGET_DB."
docker compose --env-file "$compose_env" -f "$compose_root/docker-compose.yml" \
    exec -T db sh -ec \
    'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_restore --exit-on-error --no-owner -h 127.0.0.1 --username="$POSTGRES_USER" --dbname="$1"' \
    sh "$RESTORE_TARGET_DB" < "$tmp_file"
echo "Restore completed. Verify the restored database before promoting it."
