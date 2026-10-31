#!/usr/bin/env sh
set -eu

: "${S3_BUCKET:?Set S3_BUCKET}"

retention_days=${BACKUP_RETENTION_DAYS:-30}
case "$retention_days" in
    ''|*[!0-9]*) echo "BACKUP_RETENTION_DAYS must be a positive integer." >&2; exit 2 ;;
esac
[ "$retention_days" -gt 0 ] || { echo "BACKUP_RETENTION_DAYS must be greater than zero." >&2; exit 2; }

compose_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose_env=${COMPOSE_ENV_FILE:-$compose_root/.env.production}
[ -f "$compose_env" ] || compose_env=$compose_root/.env
[ -f "$compose_env" ] || { echo "Set COMPOSE_ENV_FILE to the Compose environment file." >&2; exit 2; }
prefix=${BACKUP_PREFIX:-gaaridoc}
timestamp=$(date -u '+%Y%m%dT%H%M%SZ')
key=${prefix%/}/$timestamp.dump
tmp_file=$(mktemp)
trap 'rm -f "$tmp_file"' EXIT HUP INT TERM
chmod 600 "$tmp_file"

echo "Creating PostgreSQL custom-format backup."
docker compose --env-file "$compose_env" -f "$compose_root/docker-compose.yml" \
    exec -T db sh -ec 'export PGPASSWORD="$POSTGRES_PASSWORD"; exec pg_dump --format=custom --no-owner --username="$POSTGRES_USER" --dbname="$POSTGRES_DB"' \
    > "$tmp_file"
test -s "$tmp_file"

set --
[ -z "${S3_ENDPOINT_URL:-}" ] || set -- --endpoint-url "$S3_ENDPOINT_URL"
[ -z "${AWS_DEFAULT_REGION:-}" ] || set -- "$@" --region "$AWS_DEFAULT_REGION"
aws s3 cp "$tmp_file" "s3://$S3_BUCKET/$key" --only-show-errors "$@"
echo "Backup uploaded to s3://$S3_BUCKET/$key"

cutoff=$(date -u -d "$retention_days days ago" '+%Y-%m-%dT%H:%M:%SZ')
expired_keys=$(aws s3api list-objects-v2 --bucket "$S3_BUCKET" \
    --prefix "${prefix%/}/" --query "Contents[?LastModified<'$cutoff'].Key" \
    --output text "$@") || { echo "Could not list backups for retention cleanup." >&2; exit 1; }
printf '%s\n' "$expired_keys" | tr '\t' '\n' | while IFS= read -r old_key; do
    [ -n "$old_key" ] && [ "$old_key" != "None" ] || continue
    aws s3 rm "s3://$S3_BUCKET/$old_key" --only-show-errors "$@"
    echo "Expired backup removed: $old_key"
done
