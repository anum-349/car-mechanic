#!/bin/sh
set -eu

case "${ADMIN_URL:-}" in
    ""|*[!A-Za-z0-9_/-]*)
        echo "ADMIN_URL must be a non-empty URL path made of letters, digits, '_' or '-'." >&2
        exit 1
        ;;
esac
ADMIN_URL=${ADMIN_URL#/}
ADMIN_URL=${ADMIN_URL%/}
[ -n "$ADMIN_URL" ] || { echo "ADMIN_URL cannot be the root path." >&2; exit 1; }
export ADMIN_URL

envsubst '${ADMIN_URL}' \
    < /etc/nginx/http.d/default.conf.template \
    > /etc/nginx/http.d/default.conf
nginx -t
exec "$@"
